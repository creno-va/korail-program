"""Main PySide6 desktop window."""

from __future__ import annotations

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

from korail_program.analysis.batch import BatchAnalysisConfig, BatchAnalysisResult, run_batch_analysis
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
from korail_program.config import DEFAULT_VISION_MODEL
from korail_program.core.models import RiskLevel
from korail_program.core.timecode import format_timecode
from korail_program.runtime import (
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
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, config: BatchAnalysisConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            self.log_message.emit("분석 엔진 시작")
            result = run_batch_analysis(self.config)
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
        self._event_payloads: dict[int, dict[str, object]] = {}
        self._event_capture_paths: dict[int, Path] = {}
        self._last_result: BatchAnalysisResult | None = None
        self._analysis_worker: AnalysisWorker | None = None
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
        self.model_chip = StatusChip("Gemma4 12B 필요", "warning")
        self.ocr_chip = StatusChip("VLM OCR 대기", "warning")
        action_row.addWidget(self.runtime_chip)
        action_row.addWidget(self.model_chip)
        action_row.addWidget(self.ocr_chip)
        action_row.addStretch(1)

        self.install_model_button = ActionButton("모델 설치", icon_name="download-outline")
        self.install_model_button.clicked.connect(self.install_model)
        self.start_button = ActionButton("분석 시작", icon_name="play-circle-outline")
        self.start_button.clicked.connect(self.start_analysis)
        self.export_button = ActionButton("리포트 열기", icon_name="file-document-outline")
        self.export_button.clicked.connect(self.export_report)
        action_row.addWidget(self.install_model_button)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.export_button)

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
        self._queued_files.clear()
        self._queue_cards.clear()
        self._analysis_cards.clear()
        self._event_payloads.clear()
        self._event_capture_paths.clear()
        self._last_result = None
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

    def start_analysis(self) -> None:
        if self._analysis_worker is not None and self._analysis_worker.isRunning():
            self._log("분석이 이미 진행 중입니다.")
            return
        if not self._queued_files:
            self._log("분석 보류: 영상 파일 없음")
            QMessageBox.warning(self, "영상 없음", "분석할 영상 파일을 먼저 등록하세요.")
            return

        ollama_path = resolve_ollama_executable()
        if ollama_path is None:
            self.runtime_chip.setText("Ollama 없음")
            self.runtime_chip.set_tone("error")
            QMessageBox.warning(
                self,
                "Ollama 런타임 없음",
                "설치 파일에 Ollama 런타임이 포함되어 있지 않습니다. 최신 설치 파일로 다시 설치하세요.",
            )
            return

        self._ensure_ollama_server(str(ollama_path))
        self._prepare_analysis_cards()
        QTimer.singleShot(1600, self._start_analysis_worker)

    def _prepare_analysis_cards(self) -> None:
        self.events_list.clear_cards()
        self._event_payloads.clear()
        self._event_capture_paths.clear()
        self._last_result = None
        self.session_chip.setText("분석 준비")
        self.session_chip.set_tone("warning")
        self.progress.setValue(5)
        self.progress.set_tone("warning")
        self.start_button.setEnabled(False)
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self.events_list.set_empty_text("분석 중입니다. 이벤트가 감지되면 여기에 표시됩니다.")
        for path, card in self._queue_cards.items():
            card.set_status("대기", "warning")
            self._analysis_cards[path].set_state(
                "대기",
                "warning",
                "프레임 추출, VQA Judge, VLM OCR 준비",
                10,
            )

    def _start_analysis_worker(self) -> None:
        output_dir = user_data_dir() / "reports" / "analysis"
        config = BatchAnalysisConfig(
            inputs=list(self._queued_files),
            output_dir=output_dir,
            interval_s=10.0,
            model=DEFAULT_VISION_MODEL,
            route_hint=None,
            ffmpeg_path=resolve_ffmpeg_executable(),
            ffprobe_path=resolve_ffprobe_executable(),
            min_report_risk=RiskLevel.MEDIUM,
            ocr_backend="vlm",
            ocr_interval_s=30.0,
        )
        worker = AnalysisWorker(config)
        self._analysis_worker = worker
        worker.log_message.connect(self._log)
        worker.succeeded.connect(self._handle_analysis_succeeded)
        worker.failed.connect(self._handle_analysis_failed)
        worker.finished.connect(self._handle_analysis_finished)

        for path, card in self._queue_cards.items():
            card.set_status("분석 중", "warning")
            self._analysis_cards[path].set_state(
                "분석 중",
                "warning",
                f"{DEFAULT_VISION_MODEL} Judge + VLM OCR 실행 중",
                45,
            )
        self.session_chip.setText("분석 중")
        self.session_chip.set_tone("warning")
        self.progress.setValue(45)
        self.progress.set_tone("warning")
        self._log("배치 분석 시작")
        worker.start()

    def _handle_analysis_succeeded(self, result: BatchAnalysisResult) -> None:
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
        self.model_chip.setText("Gemma4 12B 사용")
        self.model_chip.set_tone("error" if result.aborted else "success")
        self.ocr_chip.setText(f"VLM OCR {result.ocr_observation_count}건")
        self.ocr_chip.set_tone("success" if result.ocr_observation_count else tone)

        for path, card in self._queue_cards.items():
            card.set_status(session_text, tone)
            self._analysis_cards[path].set_state(
                session_text,
                tone,
                _analysis_stage_message(result),
                100,
            )

        self._populate_events(result, empty_text=_event_empty_message(result))
        self._log(f"리포트 생성 완료: {result.report_html}")
        if result.failure_summary:
            self._log(result.failure_summary)
        if result.failure_count:
            self._log(f"처리 실패 {result.failure_count}건은 observations.json에 기록됨")

    def _handle_analysis_failed(self, message: str) -> None:
        self.progress.setValue(0)
        self.progress.set_tone("error")
        self.session_chip.setText("실패")
        self.session_chip.set_tone("error")
        for path, card in self._queue_cards.items():
            card.set_status("실패", "error")
            self._analysis_cards[path].set_state("실패", "error", message, 0)
        self._log(f"분석 실패: {message}")
        QMessageBox.warning(self, "분석 실패", message)

    def _handle_analysis_finished(self) -> None:
        self.start_button.setEnabled(True)
        self._analysis_worker = None

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
            self.runtime_chip.setText("Ollama 없음")
            self.runtime_chip.set_tone("error")
            QMessageBox.warning(
                self,
                "Ollama 런타임 없음",
                "설치 파일에 Ollama 런타임이 포함되어 있지 않습니다. 최신 설치 파일로 다시 설치하세요.",
            )
            return

        self._ensure_ollama_server(str(ollama_path))
        QTimer.singleShot(1800, lambda: self._start_model_pull(str(ollama_path)))

    def _start_model_pull(self, ollama_path: str) -> None:
        process = QProcess(self)
        self._model_install_process = process
        process.setProgram(ollama_path)
        process.setArguments(["pull", DEFAULT_VISION_MODEL])
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
        self._log(f"모델 설치 시작: ollama pull {DEFAULT_VISION_MODEL}")
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
            lambda: self._append_process_output(server.readAllStandardOutput())
        )
        server.readyReadStandardError.connect(
            lambda: self._append_process_output(server.readAllStandardError())
        )
        server.start()
        self._log("Ollama 로컬 서버 시작")

    def _append_process_output(self, payload) -> None:
        text = bytes(payload).decode("utf-8", errors="replace").strip()
        if not text:
            return
        for line in text.splitlines():
            self._log(line.strip())

    def _handle_model_install_error(self, _error) -> None:
        self.install_model_button.setEnabled(True)
        self.model_chip.setText("모델 설치 실패")
        self.model_chip.set_tone("error")
        self.ocr_chip.setText("OCR 대기")
        self.ocr_chip.set_tone("error")
        QMessageBox.warning(
            self,
            "모델 설치 실패",
            "번들 Ollama 런타임 실행에 실패했습니다. 설치 파일을 다시 설치한 뒤 재시도하세요.",
        )

    def _handle_model_install_finished(self, exit_code: int, _exit_status=None) -> None:
        self.install_model_button.setEnabled(True)
        if exit_code == 0:
            self.model_chip.setText("Gemma4 12B 설치됨")
            self.model_chip.set_tone("success")
            self.ocr_chip.setText("VLM OCR 준비")
            self.ocr_chip.set_tone("success")
            self._log(f"모델 설치 완료: {DEFAULT_VISION_MODEL}")
            return
        self.model_chip.setText("모델 설치 실패")
        self.model_chip.set_tone("error")
        self.ocr_chip.setText("OCR 대기")
        self.ocr_chip.set_tone("error")
        self._log(f"모델 설치 실패: exit_code={exit_code}")

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
            self.runtime_chip.setText("Ollama 없음")
            self.runtime_chip.set_tone("error")
        elif str(resolve_ffmpeg_executable()) == "ffmpeg" or str(resolve_ffprobe_executable()) == "ffprobe":
            self.runtime_chip.setText("FFmpeg 확인 필요")
            self.runtime_chip.set_tone("warning")
        else:
            self.runtime_chip.setText("런타임 포함")
            self.runtime_chip.set_tone("success")
        self.ocr_chip.setText("VLM OCR 준비")
        self.ocr_chip.set_tone("neutral")

    def _add_analysis_status_card(self, path: Path, queue_file: QueueFile) -> None:
        card = AnalysisStatusCard(queue_file)
        self.analysis_list.add_card(path, card, selectable=False)
        self._analysis_cards[path] = card

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
