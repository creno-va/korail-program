"""Main PySide6 desktop window."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from korail_program.analysis.batch import (
    AnalysisCancelled,
    BatchAnalysisConfig,
    BatchAnalysisProgress,
    BatchAnalysisResult,
    run_batch_analysis,
)
from korail_program.app.home_page import WorkflowHomePage
from korail_program.app.model_dialog import ModelSettingsDialog
from korail_program.app.theme import APP_STYLESHEET
from korail_program.app.video_player import VideoPlayer
from korail_program.app.widgets import (
    ActionButton,
    CardList,
    EventCard,
    ProgressTrack,
    QueueFile,
    StatusChip,
    TextPanel,
    VideoListCard,
)
from korail_program.config import (
    DEFAULT_ANALYSIS_INTERVAL_SEC,
    DEFAULT_OCR_INTERVAL_SEC,
    DEFAULT_OPENAI_API_KEY_ENV,
    DEFAULT_VISION_MODEL,
)
from korail_program.core.event_merger import format_section_label
from korail_program.core.models import RiskLevel
from korail_program.core.timecode import format_timecode
from korail_program.core.video_files import collect_video_candidates
from korail_program.model_catalog import detect_system_profile
from korail_program.runtime import (
    resolve_ffmpeg_executable,
    resolve_ffprobe_executable,
    user_data_dir,
)

DETAIL_FIELDS = ("영상", "OCR 추정 구간", "타임코드", "위험도", "OCR", "검수")


class AnalysisWorker(QThread):
    log_message = Signal(str)
    progress_updated = Signal(object)
    succeeded = Signal(object)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(self, config: BatchAnalysisConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            self.log_message.emit("분석 엔진 시작")
            config = replace(
                self.config,
                progress_callback=self.progress_updated.emit,
                cancel_callback=self.isInterruptionRequested,
            )
            result = run_batch_analysis(config)
        except AnalysisCancelled as exc:
            self.cancelled.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._queued_files: dict[Path, QueueFile] = {}
        self._analysis_cards: dict[Path, VideoListCard] = {}
        self._analysis_results: dict[Path, BatchAnalysisResult] = {}
        self._event_payloads: dict[int, dict[str, object]] = {}
        self._last_result: BatchAnalysisResult | None = None
        self._analysis_workers: dict[Path, AnalysisWorker] = {}
        self._pending_analysis_path: Path | None = None
        self._selected_video_path: Path | None = None
        self._last_progress_log_key: tuple[str, str, int, int] | None = None
        self._selected_model = self._load_selected_model()
        self._openai_api_key = self._load_openai_api_key()
        self._system_profile = detect_system_profile()

        self.setWindowTitle("전차선로 지장수목 분석")
        self.resize(1480, 920)
        self.setMinimumSize(1180, 760)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_theme()
        self._refresh_runtime_status()

    def _build_ui(self) -> None:
        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("AppPages")
        self.home_page = WorkflowHomePage()
        self.home_page.upload_requested.connect(self._choose_files)
        self.home_page.analysis_requested.connect(self._toggle_selected_analysis)
        self.home_page.report_requested.connect(self.save_pdf_report)
        self.home_page.detail_requested.connect(self._show_detail_page)
        self.detail_page = self._build_detail_page()
        self.page_stack.addWidget(self.home_page)
        self.page_stack.addWidget(self.detail_page)
        self.page_stack.setCurrentWidget(self.home_page)
        self.setCentralWidget(self.page_stack)

    def _build_detail_page(self) -> QWidget:
        root = QWidget()
        root.setObjectName("DetailPage")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        navigation = QFrame()
        navigation.setObjectName("DetailNavigation")
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(12, 8, 16, 8)
        navigation_layout.setSpacing(8)
        self.back_button = ActionButton("", icon_name="arrow-left", compact=True)
        self.back_button.setToolTip("메인으로 돌아가기")
        self.back_button.clicked.connect(self._show_home_page)
        navigation_layout.addWidget(self.back_button)
        navigation_layout.addStretch(1)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("WorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_work_panel())
        splitter.addWidget(self._build_inspector_panel())
        splitter.setSizes([290, 830, 360])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        root_layout.addWidget(navigation)
        root_layout.addWidget(splitter, stretch=1)
        return root

    def _show_home_page(self) -> None:
        self.page_stack.setCurrentWidget(self.home_page)
        self._sync_primary_actions()

    def _show_detail_page(self) -> None:
        self.page_stack.setCurrentWidget(self.detail_page)
        self._sync_primary_actions()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if _local_drop_paths(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if _local_drop_paths(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = _local_drop_paths(event.mimeData())
        if paths:
            self.add_video_files(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LeftRail")
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        self.add_files_button = ActionButton(
            "새 영상 등록",
            icon_name="plus",
        )
        self.add_files_button.clicked.connect(self._choose_files)

        self.video_list_label = QLabel("등록된 영상")
        self.video_list_label.setObjectName("SectionTitle")
        self.analysis_list = CardList(
            "분석할 영상을 등록하세요.\n파일을 이곳으로 끌어다 놓아도 됩니다.",
            accept_drops=True,
        )
        self.analysis_list.files_dropped.connect(self.add_video_files)
        self.analysis_list.selection_changed.connect(self._on_analysis_selection_changed)

        list_actions = QHBoxLayout()
        list_actions.setSpacing(8)
        self.add_folder_button = ActionButton("", icon_name="folder-open-outline", compact=True)
        self.add_folder_button.setToolTip("폴더의 영상 추가")
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.more_button = ActionButton("", icon_name="dots-horizontal", compact=True)
        self.more_button.setToolTip("영상 목록 비우기")
        self.more_button.clicked.connect(self._clear_queue_with_confirm)
        list_actions.addWidget(self.add_files_button, stretch=1)
        list_actions.addWidget(self.add_folder_button)
        list_actions.addWidget(self.more_button)

        settings = QFrame()
        settings.setObjectName("SidebarSettings")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(16, 14, 16, 16)
        settings_layout.setSpacing(12)

        self.model_summary_label = QLabel(self._selected_model)
        self.model_summary_label.setObjectName("ModelName")

        self.install_model_button = ActionButton("API 및 모델 설정", icon_name="tune")
        self.install_model_button.clicked.connect(self.install_model)

        settings_layout.addWidget(self.model_summary_label)
        settings_layout.addWidget(self.install_model_button)

        layout.addWidget(self.video_list_label)
        layout.addWidget(self.analysis_list, stretch=1)
        layout.addLayout(list_actions)
        layout.addWidget(settings)
        return panel

    def _build_work_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("WorkPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(16)
        selected_info = QVBoxLayout()
        selected_info.setSpacing(4)
        self.selected_video_title = QLabel("영상을 선택하세요")
        self.selected_video_title.setObjectName("PageTitle")
        self.selected_video_meta = QLabel("왼쪽 목록에서 작업할 영상을 선택합니다.")
        self.selected_video_meta.setObjectName("Muted")
        selected_info.addWidget(self.selected_video_title)
        selected_info.addWidget(self.selected_video_meta)
        header.addLayout(selected_info)
        header.addStretch(1)
        self.session_chip = StatusChip("대기", "neutral")
        header.addWidget(self.session_chip)

        self.video_player = VideoPlayer()

        analysis_panel = QFrame()
        analysis_panel.setObjectName("AnalysisBlock")
        analysis_layout = QVBoxLayout(analysis_panel)
        analysis_layout.setContentsMargins(16, 14, 16, 16)
        analysis_layout.setSpacing(10)

        progress_header = QHBoxLayout()
        progress_title = QLabel("분석 진행도")
        progress_title.setObjectName("CardTitle")
        self.analysis_stage_label = QLabel("영상 선택 대기")
        self.analysis_stage_label.setObjectName("Muted")
        progress_header.addWidget(progress_title)
        progress_header.addStretch(1)
        progress_header.addWidget(self.analysis_stage_label)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(12)
        self.analysis_button = ActionButton(
            "분석 시작",
            icon_name="play-circle-outline",
            tone="primary",
            small=True,
        )
        self.analysis_button.clicked.connect(self._toggle_selected_analysis)
        self.progress = ProgressTrack()
        progress_row.addWidget(self.analysis_button)
        progress_row.addWidget(self.progress, stretch=1)

        analysis_layout.addLayout(progress_header)
        analysis_layout.addLayout(progress_row)

        detail_panel = QFrame()
        detail_panel.setObjectName("DetailBlock")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(16, 14, 16, 16)
        detail_layout.setSpacing(12)

        detail_header = QHBoxLayout()
        detail_title = QLabel("선택 프레임 상세")
        detail_title.setObjectName("CardTitle")
        self.detail_status_chip = StatusChip("선택 없음", "neutral")
        detail_header.addWidget(detail_title)
        detail_header.addStretch(1)
        detail_header.addWidget(self.detail_status_chip)

        fields = QFrame()
        fields.setObjectName("DetailFields")
        grid = QGridLayout(fields)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self.detail_labels: dict[str, QLabel] = {}
        for index, key in enumerate(DETAIL_FIELDS):
            row = index // 3
            column = (index % 3) * 2
            label = QLabel(key)
            label.setObjectName("Tiny")
            value = QLabel("-")
            value.setWordWrap(True)
            self.detail_labels[key] = value
            grid.addWidget(label, row, column)
            grid.addWidget(value, row, column + 1)

        self.evidence_panel = TextPanel(
            "오른쪽 프레임을 선택하면 판단 근거가 표시됩니다.",
            max_lines=12,
        )
        self.evidence_panel.setMaximumHeight(84)
        self.evidence_panel.hide()
        self.log_panel = TextPanel(max_lines=80)
        self.log_panel.hide()

        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(fields)
        detail_layout.addWidget(self.evidence_panel)

        lower_content = QWidget()
        lower_content.setObjectName("WorkScrollContent")
        lower_layout = QVBoxLayout(lower_content)
        lower_layout.setContentsMargins(0, 0, 4, 0)
        lower_layout.setSpacing(16)
        lower_layout.addWidget(analysis_panel)
        lower_layout.addWidget(detail_panel)
        lower_layout.addStretch(1)

        lower_scroll = QScrollArea()
        lower_scroll.setObjectName("WorkScroll")
        lower_scroll.setWidgetResizable(True)
        lower_scroll.setFrameShape(QFrame.Shape.NoFrame)
        lower_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lower_scroll.setMinimumHeight(250)
        lower_scroll.setWidget(lower_content)

        layout.addLayout(header)
        layout.addWidget(self.video_player, stretch=3)
        layout.addWidget(lower_scroll, stretch=2)
        return panel

    def _build_inspector_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ResultsRail")
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(440)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("분석 결과")
        title.setObjectName("PageTitle")
        self.event_count_chip = StatusChip("0건", "neutral")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.event_count_chip)

        statistics = QFrame()
        statistics.setObjectName("StatisticsPanel")
        stats_grid = QGridLayout(statistics)
        stats_grid.setContentsMargins(16, 14, 16, 14)
        stats_grid.setHorizontalSpacing(24)
        stats_grid.setVerticalSpacing(12)
        self.stat_values: dict[str, QLabel] = {}
        for index, (key, title_text) in enumerate(
            (
                ("processed", "처리 프레임"),
                ("suspicious", "의심 프레임"),
                ("events", "이벤트"),
                ("failures", "처리 실패"),
            )
        ):
            tile, value = self._stat_tile(title_text)
            self.stat_values[key] = value
            stats_grid.addWidget(tile, index // 2, index % 2)

        frames_header = QHBoxLayout()
        frames_title = QLabel("탐지 프레임")
        frames_title.setObjectName("SectionTitle")
        frames_hint = QLabel("클릭하면 해당 시점으로 이동")
        frames_hint.setObjectName("Tiny")
        frames_header.addWidget(frames_title)
        frames_header.addStretch(1)
        frames_header.addWidget(frames_hint)

        self.events_list = CardList("분석이 끝나면 탐지 프레임이 여기에 표시됩니다.")
        self.events_list.selection_changed.connect(self._update_inspector_from_event)

        self.save_report_button = ActionButton(
            "PDF 리포트 저장",
            icon_name="file-pdf-box",
        )
        self.save_report_button.clicked.connect(self.save_pdf_report)

        layout.addLayout(header)
        layout.addWidget(statistics)
        layout.addLayout(frames_header)
        layout.addWidget(self.events_list, stretch=1)
        layout.addWidget(self.save_report_button)
        return panel

    def _stat_tile(self, title: str) -> tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setObjectName("StatTile")
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        tile_layout.setSpacing(4)
        value = QLabel("0")
        value.setObjectName("StatValue")
        label = QLabel(title)
        label.setObjectName("Tiny")
        tile_layout.addWidget(value)
        tile_layout.addWidget(label)
        return tile, value

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(APP_STYLESHEET)
        self._refresh_model_summary()
        self._sync_primary_actions()

    def _load_selected_model(self) -> str:
        payload = _read_settings()
        model = str(payload.get("selected_model", "")).strip()
        return model or DEFAULT_VISION_MODEL

    def _load_openai_api_key(self) -> str:
        payload = _read_settings()
        return str(payload.get("openai_api_key", "")).strip()

    def _save_settings(self) -> None:
        settings_path = _settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "selected_model": self._selected_model,
                    "openai_api_key": self._openai_api_key,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _save_api_settings(self, model_tag: str, api_key: str) -> None:
        self._selected_model = model_tag.strip() or DEFAULT_VISION_MODEL
        self._openai_api_key = api_key.strip()
        self._save_settings()
        self._refresh_runtime_status()
        self._log(f"GPT API 설정 저장: {self._selected_model}")

    def _choose_files(self) -> None:
        dialog = QFileDialog(self, "영상 파일 선택")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilter("Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)")
        if dialog.exec():
            self.add_video_files([Path(file) for file in dialog.selectedFiles()])

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "영상 폴더 선택")
        if folder:
            self.add_video_files([Path(folder)])

    def add_video_files(self, paths: list[Path]) -> None:
        added = 0
        candidates, skipped = collect_video_candidates(paths)
        first_added: Path | None = None
        for normalized in candidates:
            if normalized in self._queued_files:
                skipped += 1
                continue

            queue_file = QueueFile(path=normalized, size_bytes=normalized.stat().st_size)
            self._queued_files[normalized] = queue_file
            self._add_video_list_card(normalized, queue_file)
            first_added = first_added or normalized
            added += 1

        if added:
            self._log(f"영상 {added}개 등록")
        if skipped:
            self._log(f"중복 또는 미지원 파일 {skipped}개 제외")
        self._refresh_header()
        if first_added is not None:
            self.analysis_list.select_key(first_added)
        self._sync_primary_actions()

    def _clear_queue_with_confirm(self) -> None:
        if not self._queued_files:
            return
        answer = QMessageBox.question(
            self,
            "대기열 비우기",
            "등록된 영상을 모두 제거할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_queue()

    def clear_queue(self) -> None:
        if self._analysis_workers:
            self._log("진행 중인 영상은 먼저 중지하세요.")
            QMessageBox.warning(
                self, "분석 진행 중", "진행 중인 영상을 먼저 중지한 뒤 대기열을 비우세요."
            )
            return
        self._queued_files.clear()
        self._analysis_cards.clear()
        self._analysis_results.clear()
        self._event_payloads.clear()
        self._last_result = None
        self._pending_analysis_path = None
        self._selected_video_path = None
        self.analysis_list.clear_cards()
        self.events_list.clear_cards()
        self._set_analysis_progress(0, "neutral")
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self.video_player.clear()
        self.selected_video_title.setText("영상을 선택하세요")
        self.selected_video_meta.setText("왼쪽 목록에서 작업할 영상을 선택합니다.")
        self.analysis_stage_label.setText("영상 선택 대기")
        self._reset_stats()
        self._clear_inspector()
        self._log("대기열 초기화")
        self._refresh_header()
        self._sync_primary_actions()

    def _remove_video_with_confirm(self, path: Path) -> None:
        if path in self._analysis_workers:
            self._log(f"진행 중인 영상은 삭제할 수 없습니다: {path.name}")
            QMessageBox.warning(self, "분석 진행 중", "먼저 해당 영상 분석을 중지하세요.")
            return
        if path not in self._queued_files:
            return
        answer = QMessageBox.question(
            self,
            "영상 제거",
            f"{path.name}을(를) 목록에서 제거할까요?\n원본 영상과 리포트 파일은 삭제하지 않습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._remove_video(path)

    def _remove_video(self, path: Path) -> None:
        result = self._analysis_results.pop(path, None)
        self._queued_files.pop(path, None)
        self._analysis_cards.pop(path, None)
        if self._pending_analysis_path == path:
            self._pending_analysis_path = None
        self.analysis_list.remove_card(path)

        if self._last_result is result:
            self._last_result = None
        if self._selected_video_path == path:
            self._selected_video_path = None
            fallback = next(iter(self._queued_files), None)
            if fallback is not None:
                self.analysis_list.select_key(fallback)
            else:
                self.events_list.set_empty_text("분석할 영상을 선택하세요.")
                self.events_list.clear_cards()
                self.event_count_chip.setText("0건")
                self.event_count_chip.set_tone("neutral")
                self.video_player.clear()
                self.selected_video_title.setText("영상을 선택하세요")
                self.selected_video_meta.setText("왼쪽 목록에서 작업할 영상을 선택합니다.")
                self.session_chip.setText("대기")
                self.session_chip.set_tone("neutral")
                self._set_analysis_progress(0, "neutral")
                self.analysis_stage_label.setText("영상 선택 대기")
                self._reset_stats()
                self._clear_inspector()
        self._refresh_header()
        self._sync_primary_actions()
        self._log(f"영상 제거: {path.name}")

    def start_analysis(self) -> None:
        if not self._queued_files:
            self._log("분석 보류: 영상 파일 없음")
            QMessageBox.warning(self, "영상 없음", "분석할 영상 파일을 먼저 등록하세요.")
            return
        path = self._selected_video_path
        if path is None or path not in self._queued_files:
            self._log("분석 보류: 왼쪽 목록에서 실행할 영상을 선택하세요.")
            QMessageBox.information(
                self,
                "분석 항목 선택",
                "왼쪽 영상 목록에서 분석할 영상을 선택하세요.",
            )
            return
        self._start_video_analysis(path)

    def _toggle_selected_analysis(self) -> None:
        path = self._selected_video_path
        if path is not None and path in self._analysis_workers:
            self._stop_video_analysis(path)
            return
        self.start_analysis()

    def _start_video_analysis(self, path: Path) -> None:
        if path in self._analysis_workers:
            self._log(f"분석이 이미 진행 중입니다: {path.name}")
            return
        active_path = self._active_analysis_path()
        if active_path is not None and active_path != path:
            self._log(f"다른 영상 분석 중: {active_path.name}")
            QMessageBox.information(
                self,
                "분석 진행 중",
                "한 번에 한 영상씩 분석합니다. 현재 영상을 완료하거나 중지한 뒤 "
                "다음 영상을 시작하세요.",
            )
            return
        if self._pending_analysis_path == path:
            self._log(f"분석 준비 중입니다: {path.name}")
            return
        self._selected_video_path = path
        self.analysis_list.select_key(path)
        if not self._has_openai_api_key():
            self._pending_analysis_path = None
            QMessageBox.warning(
                self,
                "OpenAI API key 필요",
                "분석을 시작하려면 OPENAI_API_KEY 환경변수를 설정하거나 "
                "API 설정에서 key를 저장하세요.",
            )
            self.install_model()
            return

        self._pending_analysis_path = path
        self._sync_primary_actions()
        self._prepare_video_analysis_card(path)
        self._start_analysis_worker(path)

    def _stop_video_analysis(self, path: Path) -> None:
        worker = self._analysis_workers.get(path)
        if worker is None:
            self._log(f"중지할 분석이 없습니다: {path.name}")
            return
        worker.requestInterruption()
        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_stopping()
            card.set_state("중지 요청", "warning", "현재 프레임 처리 후 중지", card.progress_value)
        self.analysis_stage_label.setText("현재 프레임 처리 후 중지")
        self._log(f"분석 중지 요청: {path.name}")
        self._sync_primary_actions()

    def _prepare_video_analysis_card(self, path: Path) -> None:
        self.events_list.clear_cards()
        self._event_payloads.clear()
        self._analysis_results.pop(path, None)
        self._last_result = None
        self._last_progress_log_key = None
        self.session_chip.setText("분석 준비")
        self.session_chip.set_tone("primary")
        self._set_analysis_progress(5, "primary")
        self.analysis_stage_label.setText("분석 환경 확인 중")
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self._reset_stats()
        self.events_list.set_empty_text("분석 중입니다. 이벤트가 감지되면 여기에 표시됩니다.")
        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_preparing()
            card.set_state("대기", "primary", "프레임 추출, VQA Judge, VLM OCR 준비", 10)
        self._sync_primary_actions()

    def _start_analysis_worker(self, path: Path) -> None:
        if path in self._analysis_workers:
            if self._pending_analysis_path == path:
                self._pending_analysis_path = None
                self._restore_analysis_card_action(path)
            return
        if path not in self._queued_files:
            if self._pending_analysis_path == path:
                self._pending_analysis_path = None
                self._restore_analysis_card_action(path)
            return
        output_dir = user_data_dir() / "reports" / "analysis" / _safe_report_dir(path)
        config = BatchAnalysisConfig(
            inputs=[path],
            output_dir=output_dir,
            interval_s=DEFAULT_ANALYSIS_INTERVAL_SEC,
            model=self._selected_model,
            openai_api_key=self._openai_api_key or None,
            route_hint=None,
            ffmpeg_path=resolve_ffmpeg_executable(),
            ffprobe_path=resolve_ffprobe_executable(),
            min_report_risk=RiskLevel.LOW,
            ocr_backend="vlm",
            ocr_interval_s=DEFAULT_OCR_INTERVAL_SEC,
        )
        worker = AnalysisWorker(config)
        self._analysis_workers[path] = worker
        if self._pending_analysis_path == path:
            self._pending_analysis_path = None
        worker.log_message.connect(self._log)
        worker.progress_updated.connect(self._handle_analysis_progress)
        worker.succeeded.connect(
            lambda result, target=path: self._handle_video_succeeded(target, result)
        )
        worker.cancelled.connect(
            lambda message, target=path: self._handle_video_cancelled(target, message)
        )
        worker.failed.connect(
            lambda message, target=path: self._handle_video_failed(target, message)
        )
        worker.finished.connect(lambda target=path: self._handle_video_finished(target))

        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_running()
            card.set_state("분석 중", "primary", f"{self._selected_model} 스캔 대기", 12)
        self.session_chip.setText("분석 중")
        self.session_chip.set_tone("primary")
        self.analysis_stage_label.setText("프레임 추출 준비")
        self._set_analysis_progress(12, "primary")
        self._log(
            f"{path.name} 분석 시작: 모델 {self._selected_model}, "
            f"배치 분석 시작: VQA {DEFAULT_ANALYSIS_INTERVAL_SEC:g}초 간격, "
            f"OCR {DEFAULT_OCR_INTERVAL_SEC:g}초 간격"
        )
        self._sync_primary_actions()
        worker.start()

    def _handle_analysis_progress(self, progress: BatchAnalysisProgress) -> None:
        if not isinstance(progress, BatchAnalysisProgress):
            return

        if progress.stage == "extracting":
            card_stage = "프레임 추출 중"
            card_percent = 18
        elif progress.stage == "judging":
            card_stage = progress.message
            card_percent = _video_card_progress(progress)
        elif progress.stage == "reporting":
            card_stage = progress.message
            card_percent = 96
        else:
            card_stage = "분석 준비"
            card_percent = progress.percent
        self._set_progress_card(progress, card_stage, card_percent)

        progress_path = progress.video_path.resolve() if progress.video_path else None
        if progress_path is not None and progress_path != self._selected_video_path:
            self._log_progress_if_needed(progress)
            return

        self._set_analysis_progress(progress.percent, "primary")
        self.session_chip.set_tone("primary")
        self.analysis_stage_label.setText(progress.message)
        self.stat_values["processed"].setText(
            f"{progress.processed_frame_count}/{max(0, progress.total_frame_count)}"
        )

        if progress.stage == "extracting":
            self.session_chip.setText("프레임 추출")
        elif progress.stage == "judging":
            total = max(1, progress.total_frame_count)
            self.session_chip.setText(f"{progress.processed_frame_count}/{total} 프레임")
        elif progress.stage == "reporting":
            self.session_chip.setText("리포트 생성")
        else:
            self.session_chip.setText("분석 준비")

        self._log_progress_if_needed(progress)

    def _log_progress_if_needed(self, progress: BatchAnalysisProgress) -> None:
        if _should_log_progress(progress, self._last_progress_log_key):
            self._last_progress_log_key = (
                progress.stage,
                str(progress.video_path or ""),
                progress.video_index,
                progress.frame_index,
            )
            self._log(progress.message)

    def _set_progress_card(
        self,
        progress: BatchAnalysisProgress,
        stage_text: str,
        percent: int,
    ) -> None:
        if progress.video_path is None:
            return
        path = progress.video_path.resolve()
        card = self._analysis_cards.get(path)
        if card is None:
            return
        card.set_running()
        card.set_state("분석 중", "primary", stage_text, percent)

    def _handle_video_succeeded(self, path: Path, result: BatchAnalysisResult) -> None:
        self._analysis_results[path] = result
        session_text, tone = _result_status(result)

        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_finished()
            card.set_state(session_text, tone, _analysis_stage_message(result), 100)

        if self._selected_video_path == path:
            self._last_result = result
            self._set_analysis_progress(100, tone)
            self.session_chip.setText(session_text)
            self.session_chip.set_tone(tone)
            self.analysis_stage_label.setText(_analysis_stage_message(result))
            self.event_count_chip.setText(f"{result.event_count}건")
            self.event_count_chip.set_tone("success" if result.event_count else tone)
            self._update_result_stats(result)
            self._populate_events(result, empty_text=_event_empty_message(result))
        self._log(f"{path.name} PDF 리포트 생성 완료: {result.report_pdf}")
        if result.failure_summary:
            self._log(result.failure_summary)
        if result.failure_count:
            self._log(f"처리 실패 {result.failure_count}건은 observations.json에 기록됨")
        self._sync_primary_actions()

    def _handle_video_cancelled(self, path: Path, message: str) -> None:
        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_finished()
            card.set_state("중지됨", "warning", message, card.progress_value)
        if self._selected_video_path == path:
            self._set_analysis_progress_tone("warning")
            self.session_chip.setText("중지됨")
            self.session_chip.set_tone("warning")
            self.analysis_stage_label.setText(message)
        self._log(f"{path.name} 분석 중지됨")
        self._sync_primary_actions()

    def _handle_video_failed(self, path: Path, message: str) -> None:
        card = self._analysis_cards.get(path)
        if card is not None:
            card.set_finished()
            card.set_state("실패", "error", message, 0)
        if self._selected_video_path == path:
            self._set_analysis_progress(0, "error")
            self.session_chip.setText("실패")
            self.session_chip.set_tone("error")
            self.analysis_stage_label.setText(message)
            self.stat_values["failures"].setText("1+")
        self._log(f"{path.name} 분석 실패: {message}")
        self._sync_primary_actions()
        QMessageBox.warning(self, "분석 실패", message)

    def _handle_video_finished(self, path: Path) -> None:
        self._analysis_workers.pop(path, None)
        self._sync_primary_actions()

    def _populate_events(
        self, result: BatchAnalysisResult, *, empty_text: str | None = None
    ) -> None:
        if empty_text:
            self.events_list.set_empty_text(empty_text)
        self.events_list.clear_cards()
        self._event_payloads.clear()

        events_payload = json.loads(result.events_json.read_text(encoding="utf-8"))
        observations_payload = json.loads(result.observations_json.read_text(encoding="utf-8"))
        video_lookup = {
            int(item["video_id"]): Path(str(item["file_path"])).name
            for item in observations_payload.get("videos", [])
        }
        records = observations_payload.get("records", [])

        frame_entries = _build_frame_entries(events_payload, records)
        for index, (frame_payload, capture_path) in enumerate(frame_entries, start=1):
            self._event_payloads[index] = frame_payload
            video_name = video_lookup.get(int(frame_payload.get("video_id", 0)), "영상")
            self.events_list.add_card(
                index,
                EventCard(frame_payload, video_name=video_name, capture_path=capture_path),
            )

        if self._event_payloads:
            self.events_list.select_key(next(iter(self._event_payloads)))

    def install_model(self) -> None:
        self._open_model_dialog()

    def _open_model_dialog(self) -> None:
        dialog = ModelSettingsDialog(
            current_model=self._selected_model,
            api_key=self._openai_api_key,
            profile=self._system_profile,
            parent=self,
        )
        dialog.settings_saved.connect(self._save_api_settings)
        dialog.exec()

    def save_pdf_report(self) -> None:
        if self._last_result is None:
            QMessageBox.information(self, "저장할 리포트 없음", "먼저 분석을 완료하세요.")
            return
        source = self._last_result.report_pdf
        if not source.exists():
            QMessageBox.warning(self, "PDF 없음", "PDF 리포트 파일을 찾을 수 없습니다.")
            return

        documents_dir = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        default_dir = Path(documents_dir) if documents_dir else Path.home()
        video_stem = (
            self._selected_video_path.stem
            if self._selected_video_path is not None
            else "지장수목_분석"
        )
        target_name = default_dir / f"{video_stem}_리포트.pdf"
        target, _ = QFileDialog.getSaveFileName(
            self,
            "PDF 리포트 저장",
            str(target_name),
            "PDF Files (*.pdf)",
        )
        if not target:
            return

        target_path = Path(target)
        if target_path.suffix.lower() != ".pdf":
            target_path = target_path.with_suffix(".pdf")
        try:
            if source.resolve() != target_path.resolve():
                shutil.copy2(source, target_path)
        except OSError as exc:
            QMessageBox.warning(self, "PDF 저장 실패", str(exc))
            return

        self._log(f"PDF 리포트 저장: {target_path}")
        QMessageBox.information(self, "PDF 저장 완료", str(target_path))

    def _update_inspector_from_event(self, key: object) -> None:
        event = self._event_payloads.get(int(key))
        if event is None:
            return

        self.detail_status_chip.setText("결과 선택")
        self.detail_status_chip.set_tone("warning")
        section_start = event.get("section_start", "구간 미확인")
        section_end = event.get("section_end", "구간 미확인")
        section = format_section_label(section_start, section_end)
        start_ms = int(event.get("start_time_ms", 0))
        end_ms = int(event.get("end_time_ms", start_ms))
        frame_time_ms = int(event.get("frame_time_ms", start_ms))
        risk = RiskLevel.coerce(event.get("risk_level"))
        video_name = self._selected_video_path.name if self._selected_video_path else "-"
        self.detail_labels["영상"].setText(video_name)
        self.detail_labels["OCR 추정 구간"].setText(section)
        self.detail_labels["타임코드"].setText(
            f"{format_timecode(start_ms)} - {format_timecode(end_ms)}"
        )
        self.detail_labels["위험도"].setText(risk.value)
        self.detail_labels["OCR"].setText("VLM OCR 구간 매핑")
        self.detail_labels["검수"].setText(str(event.get("review_status", "미확인")))
        self.evidence_panel.show()
        self.evidence_panel.set_text(str(event.get("summary", "")))
        self.video_player.seek(frame_time_ms)

    def _on_analysis_selection_changed(self, key: object) -> None:
        path = Path(str(key))
        if path in self._queued_files:
            self._show_video_details(path)
            return
        self._selected_video_path = None
        self._last_result = None
        self.events_list.set_empty_text("분석할 영상을 선택하세요.")
        self.events_list.clear_cards()
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self.video_player.clear()
        self.selected_video_title.setText("영상을 선택하세요")
        self.selected_video_meta.setText("왼쪽 목록에서 작업할 영상을 선택합니다.")
        self._reset_stats()
        self._clear_inspector()
        self._sync_primary_actions()

    def _show_video_details(self, path: Path) -> None:
        queue_file = self._queued_files.get(path)
        if queue_file is None:
            return
        self._selected_video_path = path
        self.video_player.set_video(path)
        self.selected_video_title.setText(queue_file.display_name)
        self.selected_video_meta.setText(f"{queue_file.size_label} · {queue_file.path}")
        self.detail_status_chip.setText("영상 선택")
        self.detail_status_chip.set_tone("neutral")
        self.detail_labels["영상"].setText(queue_file.display_name)
        self.detail_labels["OCR 추정 구간"].setText("분석 전")
        self.detail_labels["타임코드"].setText("-")
        self.detail_labels["위험도"].setText("-")
        self.detail_labels["OCR"].setText("분석 전")
        self.detail_labels["검수"].setText("미확인")
        self.evidence_panel.hide()
        self.evidence_panel.clear()
        result = self._analysis_results.get(path)
        if result is not None:
            self._last_result = result
            session_text, tone = _result_status(result)
            self.session_chip.setText(session_text)
            self.session_chip.set_tone(tone)
            self._set_analysis_progress(100, tone)
            self._populate_events(result, empty_text=_event_empty_message(result))
            self.event_count_chip.setText(f"{result.event_count}건")
            self.event_count_chip.set_tone("success" if result.event_count else "neutral")
            self._update_result_stats(result)
            self.analysis_stage_label.setText(_analysis_stage_message(result))
        else:
            self._last_result = None
            self.events_list.set_empty_text("분석 결과가 생성되면 이벤트가 카드로 정리됩니다.")
            self.events_list.clear_cards()
            self.event_count_chip.setText("0건")
            self.event_count_chip.set_tone("neutral")
            self._reset_stats()
            card = self._analysis_cards.get(path)
            if path in self._analysis_workers and card is not None:
                self.session_chip.setText("분석 중")
                self.session_chip.set_tone("primary")
                self._set_analysis_progress(card.progress_value, "primary")
                self.analysis_stage_label.setText(card.stage_text)
            elif path == self._pending_analysis_path:
                self.session_chip.setText("분석 준비")
                self.session_chip.set_tone("primary")
                self._set_analysis_progress(5, "primary")
                self.analysis_stage_label.setText("분석 환경 확인 중")
            else:
                self.session_chip.setText("대기")
                self.session_chip.set_tone("neutral")
                self._set_analysis_progress(0, "neutral")
                self.analysis_stage_label.setText("분석 시작 대기")
        self._sync_primary_actions()

    def _clear_inspector(self) -> None:
        self.detail_status_chip.setText("선택 없음")
        self.detail_status_chip.set_tone("neutral")
        for value in self.detail_labels.values():
            value.setText("-")
        self.evidence_panel.hide()
        self.evidence_panel.clear()

    def _reset_stats(self) -> None:
        for value in self.stat_values.values():
            value.setText("0")

    def _update_result_stats(self, result: BatchAnalysisResult) -> None:
        self.stat_values["processed"].setText(str(result.sampled_frame_count))
        self.stat_values["suspicious"].setText(str(result.suspicious_frame_count))
        self.stat_values["events"].setText(str(result.event_count))
        self.stat_values["failures"].setText(str(result.failure_count))

    def _refresh_header(self) -> None:
        count = len(self._queued_files)
        self.video_list_label.setText(f"등록된 영상 · {count}")

    def _has_openai_api_key(self) -> bool:
        return bool(self._openai_api_key or os.environ.get(DEFAULT_OPENAI_API_KEY_ENV))

    def _refresh_runtime_status(self) -> None:
        if not self._has_openai_api_key():
            status = "OpenAI API key 설정이 필요합니다."
        elif (
            str(resolve_ffmpeg_executable()) == "ffmpeg"
            or str(resolve_ffprobe_executable()) == "ffprobe"
        ):
            status = "FFmpeg 실행 경로를 확인하세요."
        else:
            status = "API 및 분석 환경이 준비되었습니다."
        self.install_model_button.setToolTip(status)
        self._refresh_model_summary()

    def _add_video_list_card(self, path: Path, queue_file: QueueFile) -> None:
        card = VideoListCard(queue_file)
        card.remove_requested.connect(lambda target=path: self._remove_video_with_confirm(target))
        self.analysis_list.add_card(path, card)
        self._analysis_cards[path] = card

    def _refresh_model_summary(self) -> None:
        if not hasattr(self, "model_summary_label"):
            return
        self.model_summary_label.setText(self._selected_model)

    def _active_analysis_path(self) -> Path | None:
        if self._analysis_workers:
            return next(iter(self._analysis_workers))
        return self._pending_analysis_path

    def _restore_analysis_card_action(self, path: Path) -> None:
        card = self._analysis_cards.get(path)
        if card is None:
            return
        if path in self._analysis_results:
            card.set_finished()
            return
        card.set_idle()

    def _set_analysis_progress(self, value: int, tone: str) -> None:
        self.progress.setValue(value)
        self.progress.set_tone(tone)
        self.home_page.set_progress(value, tone)

    def _set_analysis_progress_tone(self, tone: str) -> None:
        self.progress.set_tone(tone)
        self.home_page.set_progress_tone(tone)

    def _configure_analysis_actions(
        self,
        *,
        text: str,
        home_text: str,
        icon: str,
        tone: str,
        tooltip: str,
        enabled: bool,
        home_tone: str | None = None,
    ) -> None:
        self.analysis_button.setText(text)
        self.analysis_button.set_icon(icon)
        self.analysis_button.set_tone(tone)
        self.analysis_button.setToolTip(tooltip)
        self.analysis_button.setEnabled(enabled)
        self.home_page.set_analysis_action(
            text=home_text,
            icon=icon,
            tone=home_tone or tone,
            tooltip=tooltip,
            enabled=enabled,
        )

    def _sync_home_steps(self) -> None:
        has_video = bool(self._queued_files)
        has_report = self._last_result is not None
        selected_path = (
            self._selected_video_path if self._selected_video_path in self._queued_files else None
        )
        self.home_page.set_workflow_state(
            has_video=has_video,
            has_report=has_report,
            selected_file=selected_path.name if selected_path is not None else None,
        )

    def _sync_primary_actions(self) -> None:
        if not hasattr(self, "analysis_button"):
            return
        active_path = self._active_analysis_path()
        selected_path = (
            self._selected_video_path if self._selected_video_path in self._queued_files else None
        )

        if active_path is not None:
            if active_path == selected_path:
                worker = self._analysis_workers.get(active_path)
                if worker is not None and worker.isInterruptionRequested():
                    self._configure_analysis_actions(
                        text="중지 중",
                        home_text="중지 중",
                        icon="stop-circle-outline",
                        tone="neutral",
                        tooltip="현재 프레임 처리 후 분석을 중지합니다.",
                        enabled=False,
                    )
                elif worker is not None:
                    self._configure_analysis_actions(
                        text="분석 정지",
                        home_text="분석 정지",
                        icon="stop-circle-outline",
                        tone="error",
                        tooltip="현재 분석 중지",
                        enabled=True,
                    )
                else:
                    self._configure_analysis_actions(
                        text="준비 중",
                        home_text="준비 중",
                        icon="play-circle-outline",
                        tone="neutral",
                        tooltip="GPT API 설정과 분석 준비 상태를 확인하는 중입니다.",
                        enabled=False,
                    )
            else:
                self._configure_analysis_actions(
                    text="분석 중",
                    home_text="분석 중",
                    icon="play-circle-outline",
                    tone="neutral",
                    tooltip="한 번에 한 영상만 분석합니다.",
                    enabled=False,
                )
        elif selected_path is not None:
            self._configure_analysis_actions(
                text="분석 시작",
                home_text="분석",
                icon="play-circle-outline",
                tone="primary",
                home_tone="neutral" if self._last_result is not None else "primary",
                tooltip="선택한 영상 분석 시작",
                enabled=True,
            )
        else:
            self._configure_analysis_actions(
                text="분석 시작",
                home_text="분석",
                icon="play-circle-outline",
                tone="neutral",
                tooltip="영상을 먼저 업로드하세요.",
                enabled=False,
            )

        for path, card in self._analysis_cards.items():
            if path == self._pending_analysis_path:
                card.set_preparing()
        self.save_report_button.setEnabled(self._last_result is not None)
        self._sync_home_steps()

    def _log(self, message: str) -> None:
        self.log_panel.append(message)


def _local_drop_paths(mime_data) -> list[Path]:
    if not mime_data.hasUrls():
        return []
    return [Path(url.toLocalFile()) for url in mime_data.urls() if url.isLocalFile()]


def _event_empty_message(result: BatchAnalysisResult) -> str:
    if result.event_count:
        return "분석 결과가 생성되면 이벤트가 카드로 정리됩니다."
    if result.aborted:
        return (
            "모델 호출 오류로 분석이 중단되었습니다. "
            "리포트의 처리 상태와 실행 로그에서 GPT API 오류를 확인하세요."
        )
    if result.failure_count:
        return (
            "기준 위험도에 걸리는 이벤트는 없지만 일부 프레임 처리 실패가 있습니다. "
            "리포트의 처리 실패 항목을 확인하세요."
        )
    return (
        "분석 완료: 낮음 이상으로 분류된 의심 이벤트가 없습니다. "
        "필요하면 더 짧은 샘플링 간격으로 다시 분석하세요."
    )


def _result_status(result: BatchAnalysisResult) -> tuple[str, str]:
    if result.aborted:
        return "중단", "error"
    if result.failure_count:
        return "완료/확인 필요", "warning"
    return "완료", "success"


def _analysis_stage_message(result: BatchAnalysisResult) -> str:
    if result.aborted:
        return result.failure_summary or "모델 호출 오류로 분석 중단"
    if result.failure_count:
        return f"리포트 생성 완료 / 처리 실패 {result.failure_count}건 확인 필요"
    if result.event_count:
        return f"리포트 생성 완료 / 이벤트 {result.event_count}건"
    return "리포트 생성 완료 / 기준 위험도 이벤트 없음"


def _video_card_progress(progress: BatchAnalysisProgress) -> int:
    if progress.frame_count <= 0:
        return 25
    ratio = progress.frame_index / progress.frame_count
    return max(25, min(95, 20 + int(ratio * 72)))


def _should_log_progress(
    progress: BatchAnalysisProgress,
    last_key: tuple[str, str, int, int] | None,
) -> bool:
    key = (
        progress.stage,
        str(progress.video_path or ""),
        progress.video_index,
        progress.frame_index,
    )
    if key == last_key:
        return False
    if progress.stage != "judging":
        return True
    if progress.frame_index <= 1 or progress.frame_index == progress.frame_count:
        return True
    return progress.frame_index % 5 == 0


def _settings_path() -> Path:
    return user_data_dir() / "settings.json"


def _read_settings() -> dict[str, object]:
    settings_path = _settings_path()
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_report_dir(path: Path) -> str:
    stem = path.stem.strip() or "video"
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in stem)
    return safe[:80] or "video"


def _build_frame_entries(
    events_payload: object,
    records_payload: object,
) -> list[tuple[dict[str, object], Path | None]]:
    events = (
        [item for item in events_payload if isinstance(item, dict)]
        if isinstance(events_payload, list)
        else []
    )
    records = records_payload if isinstance(records_payload, list) else []
    entries: list[tuple[dict[str, object], Path | None]] = []

    for record in records:
        if not isinstance(record, dict) or not record.get("capture_path"):
            continue
        observation = record.get("observation")
        if not isinstance(observation, dict):
            continue
        video_id = int(observation.get("video_id", record.get("video_id", 0)))
        frame_time_ms = int(observation.get("video_time_ms", record.get("video_time_ms", 0)))
        event = _find_event_for_frame(events, video_id=video_id, frame_time_ms=frame_time_ms)
        payload = dict(event) if event is not None else {}
        payload.update(
            {
                "video_id": video_id,
                "frame_time_ms": frame_time_ms,
                "start_time_ms": payload.get("start_time_ms", frame_time_ms),
                "end_time_ms": payload.get("end_time_ms", frame_time_ms),
                "section_start": payload.get("section_start", "구간 미확인"),
                "section_end": payload.get("section_end", "구간 미확인"),
                "risk_level": observation.get("risk_level", payload.get("risk_level", "없음")),
                "summary": observation.get("evidence") or payload.get("summary", ""),
            }
        )
        entries.append((payload, Path(str(record["capture_path"]))))

    if entries:
        return sorted(
            entries,
            key=lambda item: (
                int(item[0].get("video_id", 0)),
                int(item[0].get("frame_time_ms", 0)),
            ),
        )

    for event in events:
        entries.append((dict(event), _find_capture_for_event(event, records)))
    return entries


def _find_event_for_frame(
    events: list[dict[str, object]],
    *,
    video_id: int,
    frame_time_ms: int,
) -> dict[str, object] | None:
    for event in events:
        if int(event.get("video_id", 0)) != video_id:
            continue
        start_ms = int(event.get("start_time_ms", 0))
        end_ms = int(event.get("end_time_ms", start_ms))
        if start_ms <= frame_time_ms < end_ms:
            return event
    return None


def _find_capture_for_event(event: dict[str, object], records: list[object]) -> Path | None:
    video_id = int(event.get("video_id", 0))
    start_ms = int(event.get("start_time_ms", 0))
    end_ms = int(event.get("end_time_ms", start_ms))
    for record in records:
        if not isinstance(record, dict) or not record.get("capture_path"):
            continue
        observation = record.get("observation")
        if not isinstance(observation, dict):
            continue
        if int(observation.get("video_id", 0)) != video_id:
            continue
        video_time_ms = int(observation.get("video_time_ms", 0))
        if start_ms <= video_time_ms < end_ms:
            return Path(str(record["capture_path"]))
    return None
