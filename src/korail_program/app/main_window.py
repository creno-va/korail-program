"""Main PySide6 desktop window."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
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
from korail_program.app.model_dialog import ModelSettingsDialog
from korail_program.app.theme import APP_STYLESHEET
from korail_program.app.widgets import (
    ActionButton,
    AnalysisStatusCard,
    CardList,
    EventCard,
    ProgressTrack,
    QueueCard,
    QueueFile,
    StatusChip,
    TextPanel,
    horizontal_divider,
)
from korail_program.config import (
    DEFAULT_ANALYSIS_INTERVAL_SEC,
    DEFAULT_OCR_INTERVAL_SEC,
    DEFAULT_VISION_MODEL,
)
from korail_program.core.models import RiskLevel
from korail_program.core.timecode import format_timecode
from korail_program.model_catalog import detect_system_profile, recommend_model
from korail_program.runtime import (
    bundled_ollama_executable,
    bundled_ollama_runtime_ready,
    list_installed_ollama_models,
    ollama_process_environment,
    resolve_ffmpeg_executable,
    resolve_ffprobe_executable,
    resolve_ollama_executable,
    user_data_dir,
)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
DETAIL_FIELDS = ("영상", "구간", "타임코드", "위험도", "OCR", "검수")


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
        self._queue_cards: dict[Path, QueueCard] = {}
        self._analysis_cards: dict[Path, AnalysisStatusCard] = {}
        self._analysis_results: dict[Path, BatchAnalysisResult] = {}
        self._event_payloads: dict[int, dict[str, object]] = {}
        self._event_capture_paths: dict[int, Path] = {}
        self._last_result: BatchAnalysisResult | None = None
        self._analysis_workers: dict[Path, AnalysisWorker] = {}
        self._selected_video_path: Path | None = None
        self._last_progress_log_key: tuple[str, str, int, int] | None = None
        self._selected_model = self._load_selected_model()
        self._system_profile = detect_system_profile()
        self._pending_install_model: str | None = None
        self._model_install_process: QProcess | None = None
        self._ollama_server_process: QProcess | None = None

        self.setWindowTitle("전차선로 지장수목 분석")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)
        self._build_ui()
        self._apply_theme()
        self._refresh_runtime_status()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("WorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_work_panel())
        splitter.addWidget(self._build_inspector_panel())
        splitter.setSizes([320, 720, 360])

        root_layout.addWidget(splitter, stretch=1)
        self.setCentralWidget(root)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LeftRail")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("영상")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.queue_count_chip = StatusChip("0개", "neutral")
        header.addWidget(self.queue_count_chip)

        self.queue_list = CardList(
            "mp4, avi, mov, mkv 파일을 드래그하거나 아래 버튼으로 추가하세요.",
            accept_drops=True,
        )
        self.queue_list.files_dropped.connect(self.add_video_files)
        self.queue_list.selection_changed.connect(self._on_queue_selection_changed)

        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(8)
        self.add_files_button = ActionButton("영상 추가", icon_name="folder-plus-outline")
        self.add_files_button.clicked.connect(self._choose_files)
        self.more_button = ActionButton("", icon_name="dots-horizontal", compact=True)
        self.more_button.setToolTip("대기열 비우기")
        self.more_button.clicked.connect(self._clear_queue_with_confirm)
        bottom_actions.addWidget(self.add_files_button, stretch=1)
        bottom_actions.addWidget(self.more_button)

        layout.addLayout(header)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.queue_list, stretch=1)
        layout.addWidget(horizontal_divider())
        layout.addLayout(bottom_actions)
        return panel

    def _build_work_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        action_row = QHBoxLayout()
        title = QLabel("분석 작업")
        title.setObjectName("SectionTitle")
        action_row.addWidget(title)
        self.runtime_chip = StatusChip("런타임 점검", "warning")
        self.model_chip = StatusChip(f"{self._selected_model} 필요", "warning")
        self.ocr_chip = StatusChip("VLM OCR 대기", "warning")
        action_row.addWidget(self.runtime_chip)
        action_row.addWidget(self.model_chip)
        action_row.addWidget(self.ocr_chip)
        action_row.addStretch(1)

        action_panel = QFrame()
        action_panel.setObjectName("WorkflowCard")
        action_panel_layout = QVBoxLayout(action_panel)
        action_panel_layout.setContentsMargins(12, 12, 12, 12)
        action_panel_layout.setSpacing(10)

        model_row = QHBoxLayout()
        model_title = QLabel("모델")
        model_title.setObjectName("CardTitle")
        self.model_summary_label = QLabel(self._selected_model)
        self.model_summary_label.setObjectName("PanelText")
        self.recommendation_chip = StatusChip("추천 확인", "neutral")
        model_row.addWidget(model_title)
        model_row.addWidget(self.model_summary_label)
        model_row.addWidget(self.recommendation_chip)
        model_row.addStretch(1)

        action_buttons = QHBoxLayout()
        self.install_model_button = ActionButton("모델 설정", icon_name="tune")
        self.install_model_button.clicked.connect(self.install_model)
        self.start_button = ActionButton("선택 영상 분석", icon_name="play-circle-outline")
        self.start_button.clicked.connect(self.start_analysis)
        self.export_button = ActionButton("리포트 열기", icon_name="file-document-outline")
        self.export_button.clicked.connect(self.export_report)
        action_buttons.addWidget(self.install_model_button)
        action_buttons.addWidget(self.start_button)
        action_buttons.addWidget(self.export_button)
        action_buttons.addStretch(1)

        action_panel_layout.addLayout(model_row)
        action_panel_layout.addLayout(action_buttons)

        status_header = QHBoxLayout()
        status_title = QLabel("영상별 분석 로그")
        status_title.setObjectName("SectionTitle")
        self.session_chip = StatusChip("대기", "neutral")
        status_header.addWidget(status_title)
        status_header.addStretch(1)
        status_header.addWidget(self.session_chip)

        self.analysis_list = CardList("영상을 추가하면 파일별 분석 진행률이 표시됩니다.")

        result_header = QHBoxLayout()
        result_title = QLabel("탐지 이벤트")
        result_title.setObjectName("SectionTitle")
        self.event_count_chip = StatusChip("0건", "neutral")
        result_header.addWidget(result_title)
        result_header.addStretch(1)
        result_header.addWidget(self.event_count_chip)

        self.events_list = CardList("분석 결과가 생성되면 이벤트가 카드로 정리됩니다.")
        self.events_list.selection_changed.connect(self._update_inspector_from_event)

        self.progress = ProgressTrack()

        layout.addLayout(action_row)
        layout.addWidget(action_panel)
        layout.addWidget(horizontal_divider())
        layout.addLayout(status_header)
        layout.addWidget(self.analysis_list, stretch=2)
        layout.addWidget(horizontal_divider())
        layout.addLayout(result_header)
        layout.addWidget(self.events_list, stretch=3)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.progress)
        return panel

    def _build_inspector_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Inspector")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("상세")
        title.setObjectName("SectionTitle")
        self.detail_status_chip = StatusChip("선택 없음", "neutral")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.detail_status_chip)

        self.capture_placeholder = QLabel("캡처 프레임")
        self.capture_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.capture_placeholder.setMinimumHeight(210)
        self.capture_placeholder.setObjectName("CaptureBox")

        fields = QFrame()
        fields.setObjectName("MetricCard")
        grid = QGridLayout(fields)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.detail_labels: dict[str, QLabel] = {}
        for row, key in enumerate(DETAIL_FIELDS):
            label = QLabel(key)
            label.setObjectName("Muted")
            value = QLabel("-")
            value.setWordWrap(True)
            self.detail_labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        evidence_label = QLabel("Judge 판단 근거")
        evidence_label.setObjectName("SectionTitle")
        self.evidence_panel = TextPanel("이벤트를 선택하면 판단 근거가 표시됩니다.", max_lines=20)
        self.evidence_panel.setMinimumHeight(150)

        log_label = QLabel("실행 로그")
        log_label.setObjectName("SectionTitle")
        self.log_panel = TextPanel(max_lines=80)
        self.log_panel.setMaximumHeight(150)

        layout.addLayout(header)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.capture_placeholder)
        layout.addWidget(horizontal_divider())
        layout.addWidget(fields)
        layout.addWidget(horizontal_divider())
        layout.addWidget(evidence_label)
        layout.addWidget(self.evidence_panel, stretch=1)
        layout.addWidget(horizontal_divider())
        layout.addWidget(log_label)
        layout.addWidget(self.log_panel)
        return panel

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(APP_STYLESHEET)
        self._refresh_model_summary()
        self._sync_primary_actions()

    def _load_selected_model(self) -> str:
        settings_path = _settings_path()
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_VISION_MODEL
        model = str(payload.get("selected_model", "")).strip()
        return model or DEFAULT_VISION_MODEL

    def _save_selected_model(self) -> None:
        settings_path = _settings_path()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps({"selected_model": self._selected_model}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    def _select_model(self, model_tag: str) -> None:
        self._selected_model = model_tag
        self._save_selected_model()
        self._refresh_model_summary()
        self._log(f"모델 선택: {model_tag}")

    def _choose_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "영상 파일 선택",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv);;All Files (*)",
        )
        self.add_video_files([Path(file) for file in files])

    def add_video_files(self, paths: list[Path]) -> None:
        added = 0
        skipped = 0
        first_added: Path | None = None
        for path in paths:
            if not path.exists() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                skipped += 1
                continue
            normalized = path.resolve()
            if normalized in self._queued_files:
                skipped += 1
                continue

            queue_file = QueueFile(path=normalized, size_bytes=normalized.stat().st_size)
            self._queued_files[normalized] = queue_file
            queue_card = QueueCard(queue_file)
            self._queue_cards[normalized] = queue_card
            self.queue_list.add_card(normalized, queue_card)
            self._add_analysis_status_card(normalized, queue_file)
            first_added = first_added or normalized
            added += 1

        if added:
            self._log(f"영상 {added}개 등록")
        if skipped:
            self._log(f"중복 또는 미지원 파일 {skipped}개 제외")
        self._refresh_header()
        if first_added is not None:
            self.queue_list.select_key(first_added)
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
            QMessageBox.warning(self, "분석 진행 중", "진행 중인 영상을 먼저 중지한 뒤 대기열을 비우세요.")
            return
        self._queued_files.clear()
        self._queue_cards.clear()
        self._analysis_cards.clear()
        self._analysis_results.clear()
        self._event_payloads.clear()
        self._event_capture_paths.clear()
        self._last_result = None
        self._selected_video_path = None
        self.queue_list.clear_cards()
        self.analysis_list.clear_cards()
        self.events_list.clear_cards()
        self.progress.setValue(0)
        self.progress.set_tone("neutral")
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self._clear_inspector()
        self._log("대기열 초기화")
        self._refresh_header()
        self._sync_primary_actions()

    def start_analysis(self) -> None:
        if not self._queued_files:
            self._log("분석 보류: 영상 파일 없음")
            QMessageBox.warning(self, "영상 없음", "분석할 영상 파일을 먼저 등록하세요.")
            return
        path = self._selected_video_path or next(iter(self._queued_files))
        self._start_video_analysis(path)

    def _start_video_analysis(self, path: Path) -> None:
        if path in self._analysis_workers:
            self._log(f"분석이 이미 진행 중입니다: {path.name}")
            return
        self._selected_video_path = path
        self.queue_list.select_key(path)
        ollama_path = resolve_ollama_executable()
        if ollama_path is None:
            self.runtime_chip.setText(_ollama_runtime_error_label())
            self.runtime_chip.set_tone("error")
            QMessageBox.warning(
                self,
                "Ollama 런타임 오류",
                _ollama_runtime_error_message(),
            )
            return

        self._ensure_ollama_server(str(ollama_path))
        QTimer.singleShot(
            1600,
            lambda target=path, runtime=str(ollama_path): self._start_video_analysis_after_model_check(
                target,
                runtime,
            ),
        )

    def _start_video_analysis_after_model_check(self, path: Path, ollama_path: str) -> None:
        installed_models = list_installed_ollama_models(ollama_path)
        if self._selected_model not in installed_models:
            self.model_chip.setText("모델 미설치")
            self.model_chip.set_tone("warning")
            self._log(f"모델 미설치: {self._selected_model}")
            QMessageBox.information(
                self,
                "모델 미설치",
                "선택한 모델을 먼저 설치하세요. 모델 설정에서 설치할 수 있습니다.",
            )
            self._open_model_dialog(ollama_path)
            return
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
            card.set_state("중지 요청", "warning", "현재 프레임 처리 후 중지", card.progress.value())
        queue_card = self._queue_cards.get(path)
        if queue_card is not None:
            queue_card.set_status("중지 요청", "warning")
        self._log(f"분석 중지 요청: {path.name}")

    def _prepare_video_analysis_card(self, path: Path) -> None:
        self.events_list.clear_cards()
        self._event_payloads.clear()
        self._event_capture_paths.clear()
        self._analysis_results.pop(path, None)
        self._last_result = None
        self._last_progress_log_key = None
        self.session_chip.setText("분석 준비")
        self.session_chip.set_tone("warning")
        self.progress.setValue(5)
        self.progress.set_tone("warning")
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self.events_list.set_empty_text("분석 중입니다. 이벤트가 감지되면 여기에 표시됩니다.")
        queue_card = self._queue_cards.get(path)
        card = self._analysis_cards.get(path)
        if queue_card is not None:
            queue_card.set_status("대기", "warning")
        if card is not None:
            card.set_stopping()
            card.set_state("대기", "warning", "프레임 추출, VQA Judge, VLM OCR 준비", 10)
        self._sync_primary_actions()

    def _start_analysis_worker(self, path: Path) -> None:
        if path in self._analysis_workers:
            return
        if path not in self._queued_files:
            return
        output_dir = user_data_dir() / "reports" / "analysis" / _safe_report_dir(path)
        config = BatchAnalysisConfig(
            inputs=[path],
            output_dir=output_dir,
            interval_s=DEFAULT_ANALYSIS_INTERVAL_SEC,
            model=self._selected_model,
            route_hint=None,
            ffmpeg_path=resolve_ffmpeg_executable(),
            ffprobe_path=resolve_ffprobe_executable(),
            min_report_risk=RiskLevel.MEDIUM,
            ocr_backend="vlm",
            ocr_interval_s=DEFAULT_OCR_INTERVAL_SEC,
        )
        worker = AnalysisWorker(config)
        self._analysis_workers[path] = worker
        worker.log_message.connect(self._log)
        worker.progress_updated.connect(self._handle_analysis_progress)
        worker.succeeded.connect(lambda result, target=path: self._handle_video_succeeded(target, result))
        worker.cancelled.connect(lambda message, target=path: self._handle_video_cancelled(target, message))
        worker.failed.connect(lambda message, target=path: self._handle_video_failed(target, message))
        worker.finished.connect(lambda target=path: self._handle_video_finished(target))

        card = self._analysis_cards.get(path)
        queue_card = self._queue_cards.get(path)
        if queue_card is not None:
            queue_card.set_status("분석 중", "warning")
        if card is not None:
            card.set_running()
            card.set_state("분석 중", "warning", f"{self._selected_model} 스캔 대기", 12)
        self.session_chip.setText("분석 중")
        self.session_chip.set_tone("warning")
        self.progress.setValue(12)
        self.progress.set_tone("warning")
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

        self.progress.setValue(progress.percent)
        self.progress.set_tone("warning")
        self.session_chip.set_tone("warning")

        if progress.stage == "extracting":
            self.session_chip.setText("프레임 추출")
            self._set_progress_card(progress, "프레임 추출 중", 18)
        elif progress.stage == "judging":
            total = max(1, progress.total_frame_count)
            self.session_chip.setText(f"{progress.processed_frame_count}/{total} 프레임")
            self._set_progress_card(progress, progress.message, _video_card_progress(progress))
        elif progress.stage == "reporting":
            self.session_chip.setText("리포트 생성")
            self._set_progress_card(progress, progress.message, 96)
        else:
            self.session_chip.setText("분석 준비")

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
        queue_card = self._queue_cards.get(path)
        if card is None or queue_card is None:
            return
        queue_card.set_status("분석 중", "warning")
        card.set_running()
        card.set_state("분석 중", "warning", stage_text, percent)

    def _handle_video_succeeded(self, path: Path, result: BatchAnalysisResult) -> None:
        self._analysis_results[path] = result
        self._last_result = result
        self.progress.setValue(100)
        if result.aborted:
            tone = "error"
            session_text = "중단"
        elif result.failure_count:
            tone = "warning"
            session_text = "완료/확인 필요"
        else:
            tone = "success"
            session_text = "완료"
        self.progress.set_tone(tone)
        self.session_chip.setText(session_text)
        self.session_chip.set_tone(tone)
        self.event_count_chip.setText(f"{result.event_count}건")
        self.event_count_chip.set_tone("success" if result.event_count else tone)
        self.model_chip.setText(f"{self._selected_model} 사용")
        self.model_chip.set_tone("error" if result.aborted else "success")
        self.ocr_chip.setText(f"VLM OCR {result.ocr_observation_count}건")
        self.ocr_chip.set_tone("success" if result.ocr_observation_count else tone)

        queue_card = self._queue_cards.get(path)
        card = self._analysis_cards.get(path)
        if queue_card is not None:
            queue_card.set_status(session_text, tone)
        if card is not None:
            card.set_finished()
            card.set_state(session_text, tone, _analysis_stage_message(result), 100)

        if self._selected_video_path == path:
            self._populate_events(result, empty_text=_event_empty_message(result))
        self._log(f"{path.name} 리포트 생성 완료: {result.report_html}")
        if result.failure_summary:
            self._log(result.failure_summary)
        if result.failure_count:
            self._log(f"처리 실패 {result.failure_count}건은 observations.json에 기록됨")
        self._sync_primary_actions()

    def _handle_video_cancelled(self, path: Path, message: str) -> None:
        self.progress.set_tone("warning")
        self.session_chip.setText("중지됨")
        self.session_chip.set_tone("warning")
        queue_card = self._queue_cards.get(path)
        card = self._analysis_cards.get(path)
        if queue_card is not None:
            queue_card.set_status("중지됨", "warning")
        if card is not None:
            card.set_finished()
            card.set_state("중지됨", "warning", message, card.progress.value())
        self._log(f"{path.name} 분석 중지됨")
        self._sync_primary_actions()

    def _handle_video_failed(self, path: Path, message: str) -> None:
        self.progress.setValue(0)
        self.progress.set_tone("error")
        self.session_chip.setText("실패")
        self.session_chip.set_tone("error")
        queue_card = self._queue_cards.get(path)
        card = self._analysis_cards.get(path)
        if queue_card is not None:
            queue_card.set_status("실패", "error")
        if card is not None:
            card.set_finished()
            card.set_state("실패", "error", message, 0)
        self._log(f"{path.name} 분석 실패: {message}")
        self._sync_primary_actions()
        QMessageBox.warning(self, "분석 실패", message)

    def _handle_video_finished(self, path: Path) -> None:
        self._analysis_workers.pop(path, None)
        self._sync_primary_actions()

    def _populate_events(self, result: BatchAnalysisResult, *, empty_text: str | None = None) -> None:
        if empty_text:
            self.events_list.set_empty_text(empty_text)
        self.events_list.clear_cards()
        self._event_payloads.clear()
        self._event_capture_paths.clear()

        events_payload = json.loads(result.events_json.read_text(encoding="utf-8"))
        observations_payload = json.loads(result.observations_json.read_text(encoding="utf-8"))
        video_lookup = {
            int(item["video_id"]): Path(str(item["file_path"])).name
            for item in observations_payload.get("videos", [])
        }
        records = observations_payload.get("records", [])

        for index, event in enumerate(events_payload, start=1):
            if not isinstance(event, dict):
                continue
            self._event_payloads[index] = event
            capture_path = _find_capture_for_event(event, records)
            if capture_path is not None:
                self._event_capture_paths[index] = capture_path
            video_name = video_lookup.get(int(event.get("video_id", 0)), "영상")
            self.events_list.add_card(index, EventCard(event, video_name=video_name))

        if self._event_payloads:
            self.events_list.select_key(next(iter(self._event_payloads)))

    def install_model(self) -> None:
        if self._model_install_process is not None:
            if self._model_install_process.state() != QProcess.ProcessState.NotRunning:
                self._log("모델 설치가 이미 진행 중입니다.")
                return

        ollama_path = resolve_ollama_executable()
        if ollama_path is None:
            self.runtime_chip.setText(_ollama_runtime_error_label())
            self.runtime_chip.set_tone("error")
            QMessageBox.warning(
                self,
                "Ollama 런타임 오류",
                _ollama_runtime_error_message(),
            )
            return

        self._ensure_ollama_server(str(ollama_path))
        QTimer.singleShot(800, lambda: self._open_model_dialog(str(ollama_path)))

    def _open_model_dialog(self, ollama_path: str) -> None:
        installed_models = list_installed_ollama_models(ollama_path)
        dialog = ModelSettingsDialog(
            current_model=self._selected_model,
            installed_models=installed_models,
            profile=self._system_profile,
            parent=self,
        )
        dialog.model_selected.connect(self._select_model)
        dialog.install_requested.connect(lambda tag: self._start_model_pull(ollama_path, tag))
        dialog.exec()

    def _start_model_pull(self, ollama_path: str, model_tag: str) -> None:
        process = QProcess(self)
        self._model_install_process = process
        self._pending_install_model = model_tag
        process.setProgram(ollama_path)
        process.setArguments(["pull", model_tag])
        process.setProcessEnvironment(_process_environment())
        process.readyReadStandardOutput.connect(
            lambda: self._append_process_output(process.readAllStandardOutput())
        )
        process.readyReadStandardError.connect(
            lambda: self._append_process_output(process.readAllStandardError())
        )
        process.errorOccurred.connect(self._handle_model_install_error)
        process.finished.connect(self._handle_model_install_finished)

        self.install_model_button.setEnabled(False)
        self.model_chip.setText("모델 설치 중")
        self.model_chip.set_tone("warning")
        self.ocr_chip.setText("OCR 모델 공유")
        self.ocr_chip.set_tone("warning")
        self.model_summary_label.setText(f"{model_tag} 설치 중")
        self._log(f"모델 설치 시작: ollama pull {model_tag}")
        process.start()

    def _ensure_ollama_server(self, ollama_path: str) -> None:
        if self._ollama_server_process is not None:
            if self._ollama_server_process.state() != QProcess.ProcessState.NotRunning:
                return

        server = QProcess(self)
        self._ollama_server_process = server
        server.setProgram(ollama_path)
        server.setArguments(["serve"])
        server.setProcessEnvironment(_process_environment())
        server.readyReadStandardOutput.connect(
            lambda: self._append_process_output(server.readAllStandardOutput(), source="server")
        )
        server.readyReadStandardError.connect(
            lambda: self._append_process_output(server.readAllStandardError(), source="server")
        )
        server.start()
        self._log("Ollama 로컬 서버 시작")

    def _append_process_output(self, payload, *, source: str = "process") -> None:
        text = bytes(payload).decode("utf-8", errors="replace").strip()
        if not text:
            return
        for line in text.splitlines():
            cleaned = line.strip()
            if source == "server" and not _should_show_ollama_server_log(cleaned):
                continue
            self._log(cleaned)

    def _handle_model_install_error(self, _error) -> None:
        self.install_model_button.setEnabled(True)
        self._pending_install_model = None
        self.model_chip.setText("모델 설치 실패")
        self.model_chip.set_tone("error")
        self.ocr_chip.setText("OCR 대기")
        self.ocr_chip.set_tone("error")
        self.model_summary_label.setText(self._selected_model)
        QMessageBox.warning(
            self,
            "모델 설치 실패",
            "번들 Ollama 런타임 실행에 실패했습니다. 설치 파일을 다시 설치한 뒤 재시도하세요.",
        )

    def _handle_model_install_finished(self, exit_code: int, _exit_status=None) -> None:
        self.install_model_button.setEnabled(True)
        model_tag = self._pending_install_model or self._selected_model
        self._pending_install_model = None
        if exit_code == 0:
            self._select_model(model_tag)
            self.model_chip.setText(f"{model_tag} 설치됨")
            self.model_chip.set_tone("success")
            self.ocr_chip.setText("VLM OCR 준비")
            self.ocr_chip.set_tone("success")
            self._log(f"모델 설치 완료: {model_tag}")
            return
        self.model_chip.setText("모델 설치 실패")
        self.model_chip.set_tone("error")
        self.ocr_chip.setText("OCR 대기")
        self.ocr_chip.set_tone("error")
        self._log(f"모델 설치 실패: exit_code={exit_code}")
        self.model_summary_label.setText(self._selected_model)

    def export_report(self) -> None:
        if self._last_result is None:
            QMessageBox.information(self, "열 리포트 없음", "먼저 분석을 완료하세요.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_result.report_html)))

    def _update_inspector_from_event(self, key: object) -> None:
        event = self._event_payloads.get(int(key))
        if event is None:
            return

        self.detail_status_chip.setText("결과 선택")
        self.detail_status_chip.set_tone("warning")
        section = f"{event.get('section_start', '구간 미확인')} ~ {event.get('section_end', '구간 미확인')}"
        start_ms = int(event.get("start_time_ms", 0))
        end_ms = int(event.get("end_time_ms", start_ms))
        risk = RiskLevel.coerce(event.get("risk_level"))
        self.detail_labels["영상"].setText(f"video_id={event.get('video_id', '-')}")
        self.detail_labels["구간"].setText(section)
        self.detail_labels["타임코드"].setText(
            f"{format_timecode(start_ms)} - {format_timecode(end_ms)}"
        )
        self.detail_labels["위험도"].setText(risk.value)
        self.detail_labels["OCR"].setText("VLM OCR 구간 매핑")
        self.detail_labels["검수"].setText(str(event.get("review_status", "미확인")))
        self.evidence_panel.set_text(str(event.get("summary", "")))
        self._set_capture_preview(self._event_capture_paths.get(int(key)))

    def _on_queue_selection_changed(self, key: object) -> None:
        path = Path(str(key))
        queue_file = self._queued_files.get(path)
        if queue_file is None:
            return
        self._selected_video_path = path
        self.detail_status_chip.setText("영상 선택")
        self.detail_status_chip.set_tone("neutral")
        self.detail_labels["영상"].setText(queue_file.display_name)
        self.detail_labels["구간"].setText("분석 전")
        self.detail_labels["타임코드"].setText("-")
        self.detail_labels["위험도"].setText("-")
        self.detail_labels["OCR"].setText("분석 전")
        self.detail_labels["검수"].setText("미확인")
        self.evidence_panel.set_text(str(queue_file.path))
        self.capture_placeholder.setPixmap(QPixmap())
        self.capture_placeholder.setText("영상 등록됨")
        result = self._analysis_results.get(path)
        if result is not None:
            self._last_result = result
            self._populate_events(result, empty_text=_event_empty_message(result))
            self.event_count_chip.setText(f"{result.event_count}건")
            self.event_count_chip.set_tone("success" if result.event_count else "neutral")
        self._sync_primary_actions()

    def _set_capture_preview(self, path: Path | None) -> None:
        if path is None or not path.exists():
            self.capture_placeholder.setPixmap(QPixmap())
            self.capture_placeholder.setText("캡처는 리포트 폴더에 저장됩니다.")
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.capture_placeholder.setText(str(path))
            return
        scaled = pixmap.scaled(
            QSize(320, 210),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.capture_placeholder.setPixmap(scaled)

    def _clear_inspector(self) -> None:
        self.detail_status_chip.setText("선택 없음")
        self.detail_status_chip.set_tone("neutral")
        for value in self.detail_labels.values():
            value.setText("-")
        self.evidence_panel.clear()
        self.capture_placeholder.setPixmap(QPixmap())
        self.capture_placeholder.setText("캡처 프레임")

    def _refresh_header(self) -> None:
        count = len(self._queued_files)
        self.queue_count_chip.setText(f"{count}개")
        self.queue_count_chip.set_tone("success" if count else "neutral")

    def _refresh_runtime_status(self) -> None:
        if resolve_ollama_executable() is None:
            self.runtime_chip.setText(_ollama_runtime_error_label())
            self.runtime_chip.set_tone("error")
        elif str(resolve_ffmpeg_executable()) == "ffmpeg" or str(resolve_ffprobe_executable()) == "ffprobe":
            self.runtime_chip.setText("FFmpeg 확인 필요")
            self.runtime_chip.set_tone("warning")
        else:
            self.runtime_chip.setText("런타임 포함")
            self.runtime_chip.set_tone("success")
        self.ocr_chip.setText("VLM OCR 준비")
        self.ocr_chip.set_tone("neutral")
        self._refresh_model_summary()

    def _add_analysis_status_card(self, path: Path, queue_file: QueueFile) -> None:
        card = AnalysisStatusCard(queue_file)
        card.start_requested.connect(lambda target=path: self._start_video_analysis(target))
        card.stop_requested.connect(lambda target=path: self._stop_video_analysis(target))
        self.analysis_list.add_card(path, card, selectable=False)
        self._analysis_cards[path] = card

    def _refresh_model_summary(self) -> None:
        if not hasattr(self, "model_summary_label"):
            return
        recommended = recommend_model(self._system_profile)
        self.model_summary_label.setText(self._selected_model)
        self.recommendation_chip.setText(f"추천 {recommended.tag}")
        self.recommendation_chip.set_tone(
            "success" if recommended.tag == self._selected_model else "warning"
        )
        if hasattr(self, "model_chip"):
            self.model_chip.setText(f"{self._selected_model} 선택")
            self.model_chip.set_tone("success" if recommended.tag == self._selected_model else "warning")

    def _sync_primary_actions(self) -> None:
        if not hasattr(self, "start_button"):
            return
        selected = self._selected_video_path
        self.start_button.setEnabled(
            selected is not None and selected in self._queued_files and selected not in self._analysis_workers
        )
        self.export_button.setEnabled(self._last_result is not None)

    def _log(self, message: str) -> None:
        self.log_panel.append(message)


def _event_empty_message(result: BatchAnalysisResult) -> str:
    if result.event_count:
        return "분석 결과가 생성되면 이벤트가 카드로 정리됩니다."
    if result.aborted:
        return (
            "모델 호출 오류로 분석이 중단되었습니다. "
            "리포트의 처리 상태와 실행 로그에서 Ollama 오류를 확인하세요."
        )
    if result.failure_count:
        return (
            "기준 위험도에 걸리는 이벤트는 없지만 일부 프레임 처리 실패가 있습니다. "
            "리포트의 처리 실패 항목을 확인하세요."
        )
    return (
        "분석 완료: 기준 위험도(중간 이상)에 걸리는 이벤트가 없습니다. "
        "필요하면 샘플링 간격을 줄이거나 리포트 기준 위험도를 낮춰 다시 분석하세요."
    )


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
    key = (progress.stage, str(progress.video_path or ""), progress.video_index, progress.frame_index)
    if key == last_key:
        return False
    if progress.stage != "judging":
        return True
    if progress.frame_index <= 1 or progress.frame_index == progress.frame_count:
        return True
    return progress.frame_index % 5 == 0


def _should_show_ollama_server_log(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in ("error", "fatal", "panic"))


def _settings_path() -> Path:
    return user_data_dir() / "settings.json"


def _safe_report_dir(path: Path) -> str:
    stem = path.stem.strip() or "video"
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in stem)
    return safe[:80] or "video"


def _ollama_runtime_error_label() -> str:
    if bundled_ollama_executable().exists() and not bundled_ollama_runtime_ready():
        return "Ollama 손상"
    return "Ollama 없음"


def _ollama_runtime_error_message() -> str:
    if bundled_ollama_executable().exists() and not bundled_ollama_runtime_ready():
        return (
            "설치된 Ollama 런타임에 llama-server 보조 바이너리가 없습니다. "
            "최신 설치 파일로 다시 설치하세요."
        )
    return "설치 파일에 Ollama 런타임이 포함되어 있지 않습니다. 최신 설치 파일로 다시 설치하세요."


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


def _process_environment() -> QProcessEnvironment:
    env = QProcessEnvironment.systemEnvironment()
    for key, value in ollama_process_environment().items():
        env.insert(key, value)
    return env
