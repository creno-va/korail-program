"""Main PySide6 desktop window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QProcess, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.icons import ICON_ERROR, material_icon
from korail_program.app.theme import APP_STYLESHEET
from korail_program.app.widgets import (
    AnalysisStatusCard,
    DropQueueList,
    EmptyState,
    QueueCard,
    QueueFile,
    StatusChip,
    horizontal_divider,
)
from korail_program.config import DEFAULT_VISION_MODEL

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
DETAIL_FIELDS = ("영상", "구간", "타임코드", "위험도", "OCR", "검수")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._queued_files: dict[Path, QueueFile] = {}
        self._queue_cards: dict[Path, QueueCard] = {}
        self._analysis_cards: dict[Path, AnalysisStatusCard] = {}
        self._analysis_empty_item: QListWidgetItem | None = None
        self._model_install_process: QProcess | None = None
        self.setWindowTitle("전차선로 지장수목 분석")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)
        self._build_ui()
        self._apply_theme()

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

        self.queue_list = DropQueueList()
        self.queue_list.setObjectName("QueueList")
        self.queue_list.files_dropped.connect(self.add_video_files)
        self.queue_list.currentItemChanged.connect(self._on_queue_selection_changed)

        bottom_actions = QHBoxLayout()
        bottom_actions.setSpacing(8)
        self.add_files_button = QPushButton("영상 추가")
        self.add_files_button.setObjectName("MainActionButton")
        self.add_files_button.setIcon(material_icon("folder-plus-outline"))
        self.add_files_button.setIconSize(QSize(18, 18))
        self.add_files_button.clicked.connect(self._choose_files)

        self.more_button = QToolButton()
        self.more_button.setObjectName("IconButton")
        self.more_button.setIcon(material_icon("dots-horizontal"))
        self.more_button.setIconSize(QSize(20, 20))
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_button.setMenu(self._build_queue_menu())

        bottom_actions.addWidget(self.add_files_button, stretch=1)
        bottom_actions.addWidget(self.more_button)

        layout.addLayout(header)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.queue_list, stretch=1)
        layout.addWidget(horizontal_divider())
        layout.addLayout(bottom_actions)
        return panel

    def _build_queue_menu(self) -> QMenu:
        menu = QMenu(self)
        clear_action = menu.addAction(material_icon("delete-outline", color=ICON_ERROR), "대기열 비우기")
        clear_action.triggered.connect(self.clear_queue)
        return menu

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
        self.model_chip = StatusChip("Gemma4 12B 필요", "warning")
        self.ocr_chip = StatusChip("OCR 미연결", "warning")
        action_row.addWidget(self.model_chip)
        action_row.addWidget(self.ocr_chip)
        action_row.addStretch(1)

        self.install_model_button = QPushButton("모델 설치")
        self.install_model_button.setIcon(material_icon("download-outline"))
        self.install_model_button.setIconSize(QSize(18, 18))
        self.install_model_button.clicked.connect(self.install_model)
        self.start_button = QPushButton("분석 시작")
        self.start_button.setIcon(material_icon("play-circle-outline"))
        self.start_button.setIconSize(QSize(18, 18))
        self.start_button.clicked.connect(self.start_analysis)
        self.export_button = QPushButton("리포트 내보내기")
        self.export_button.setIcon(material_icon("file-export-outline"))
        self.export_button.setIconSize(QSize(18, 18))
        self.export_button.clicked.connect(self.export_report)
        action_row.addWidget(self.install_model_button)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.export_button)

        status_header = QHBoxLayout()
        status_title = QLabel("영상별 로그")
        status_title.setObjectName("SectionTitle")
        self.session_chip = StatusChip("대기", "neutral")
        status_header.addWidget(status_title)
        status_header.addStretch(1)
        status_header.addWidget(self.session_chip)

        self.analysis_list = QListWidget()
        self.analysis_list.setObjectName("AnalysisList")
        self.analysis_list.setFrameShape(QFrame.Shape.NoFrame)
        self.analysis_list.setSpacing(8)

        result_header = QHBoxLayout()
        result_title = QLabel("탐지 이벤트")
        result_title.setObjectName("SectionTitle")
        self.event_count_chip = StatusChip("0건", "neutral")
        result_header.addWidget(result_title)
        result_header.addStretch(1)
        result_header.addWidget(self.event_count_chip)

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(["상태", "위험도", "구간", "타임코드", "요약", "검수"])
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.itemSelectionChanged.connect(self._update_inspector_from_result)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        layout.addLayout(action_row)
        layout.addWidget(horizontal_divider())
        layout.addLayout(status_header)
        layout.addWidget(self.analysis_list, stretch=2)
        layout.addWidget(horizontal_divider())
        layout.addLayout(result_header)
        layout.addWidget(self.results_table, stretch=3)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.progress)

        self._show_empty_analysis_state()
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
        self.evidence_text = QPlainTextEdit()
        self.evidence_text.setReadOnly(True)
        self.evidence_text.setPlaceholderText("이벤트를 선택하면 판단 근거가 표시됩니다.")
        self.evidence_text.setMinimumHeight(150)

        log_label = QLabel("실행 로그")
        log_label.setObjectName("SectionTitle")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)

        layout.addLayout(header)
        layout.addWidget(horizontal_divider())
        layout.addWidget(self.capture_placeholder)
        layout.addWidget(horizontal_divider())
        layout.addWidget(fields)
        layout.addWidget(horizontal_divider())
        layout.addWidget(evidence_label)
        layout.addWidget(self.evidence_text, stretch=1)
        layout.addWidget(horizontal_divider())
        layout.addWidget(log_label)
        layout.addWidget(self.log)
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
            card = QueueCard(queue_file)
            self._queue_cards[normalized] = card

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(normalized))
            item.setSizeHint(QSize(260, 86))
            self.queue_list.addItem(item)
            self.queue_list.setItemWidget(item, card)
            self._add_analysis_status_card(normalized, queue_file)
            added += 1

        if added:
            self._log(f"영상 {added}개 등록")
        if skipped:
            self._log(f"중복 또는 미지원 파일 {skipped}개 제외")
        self._refresh_header()

    def clear_queue(self) -> None:
        self._queued_files.clear()
        self._queue_cards.clear()
        self._analysis_cards.clear()
        self.queue_list.clear()
        self.analysis_list.clear()
        self.results_table.setRowCount(0)
        self.progress.setValue(0)
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self._clear_inspector()
        self._show_empty_analysis_state()
        self._log("대기열 초기화")
        self._refresh_header()

    def start_analysis(self) -> None:
        if not self._queued_files:
            self._log("분석 보류: 영상 파일 없음")
            QMessageBox.warning(self, "영상 없음", "분석할 영상 파일을 먼저 등록하세요.")
            return

        self.results_table.setRowCount(0)
        total = len(self._queued_files)
        self.session_chip.setText("준비 점검")
        self.session_chip.set_tone("warning")
        self.progress.setValue(0)

        for index, (path, queue_file) in enumerate(self._queued_files.items(), start=1):
            card = self._queue_cards[path]
            analysis_card = self._analysis_cards[path]
            card.set_status("점검", "warning")
            analysis_card.set_state(
                "점검",
                "warning",
                "파일 확인 완료 / 모델, OCR 파이프라인 연결 대기",
                20,
            )
            progress = int(index / total * 35)
            self.progress.setValue(progress)
            card.set_status("연결 대기", "warning")
            analysis_card.set_state(
                "연결 대기",
                "warning",
                f"{DEFAULT_VISION_MODEL}, PaddleOCR 실행 어댑터 연결 필요",
                progress,
            )

        self.session_chip.setText("백엔드 연결 대기")
        self.session_chip.set_tone("warning")
        self.model_chip.setText("Gemma4 12B 연결 필요")
        self.model_chip.set_tone("warning")
        self.ocr_chip.setText("PaddleOCR 연결 필요")
        self.ocr_chip.set_tone("warning")
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self._log(f"분석 파이프라인 연결 대기: {DEFAULT_VISION_MODEL}/PaddleOCR 실행 단계 필요")

    def install_model(self) -> None:
        if self._model_install_process is not None:
            if self._model_install_process.state() != QProcess.ProcessState.NotRunning:
                self._log("모델 설치가 이미 진행 중입니다.")
                return

        process = QProcess(self)
        self._model_install_process = process
        process.setProgram("ollama")
        process.setArguments(["pull", DEFAULT_VISION_MODEL])
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
        self._log(f"모델 설치 시작: ollama pull {DEFAULT_VISION_MODEL}")
        process.start()

    def _append_process_output(self, payload) -> None:
        text = bytes(payload).decode("utf-8", errors="replace").strip()
        if not text:
            return
        for line in text.splitlines():
            self._log(line.strip())

    def _handle_model_install_error(self, _error) -> None:
        self.install_model_button.setEnabled(True)
        self.model_chip.setText("Ollama 필요")
        self.model_chip.set_tone("error")
        QMessageBox.warning(
            self,
            "Ollama 실행 필요",
            "모델 설치를 위해 Ollama가 설치되어 있고 실행 중이어야 합니다.",
        )

    def _handle_model_install_finished(self, exit_code: int, _exit_status=None) -> None:
        self.install_model_button.setEnabled(True)
        if exit_code == 0:
            self.model_chip.setText("Gemma4 12B 설치됨")
            self.model_chip.set_tone("success")
            self._log(f"모델 설치 완료: {DEFAULT_VISION_MODEL}")
            return
        self.model_chip.setText("모델 설치 실패")
        self.model_chip.set_tone("error")
        self._log(f"모델 설치 실패: exit_code={exit_code}")

    def export_report(self) -> None:
        if self.results_table.rowCount() == 0:
            QMessageBox.information(self, "내보낼 결과 없음", "먼저 분석 결과를 생성하세요.")
            return
        target, _ = QFileDialog.getSaveFileName(
            self,
            "리포트 저장 위치",
            "analysis_report.xlsx",
            "Excel Workbook (*.xlsx);;PDF (*.pdf)",
        )
        if target:
            self._log(f"리포트 엔진 연결 후 저장 예정: {target}")

    def _show_empty_analysis_state(self) -> None:
        self.analysis_list.clear()
        self._analysis_empty_item = QListWidgetItem()
        empty = EmptyState("영상을 추가하면 파일별 분석 로그와 진행률이 여기에 표시됩니다.")
        self._analysis_empty_item.setSizeHint(QSize(420, 96))
        self.analysis_list.addItem(self._analysis_empty_item)
        self.analysis_list.setItemWidget(self._analysis_empty_item, empty)

    def _add_analysis_status_card(self, path: Path, queue_file: QueueFile) -> None:
        if self._analysis_empty_item is not None:
            row = self.analysis_list.row(self._analysis_empty_item)
            self.analysis_list.takeItem(row)
            self._analysis_empty_item = None

        card = AnalysisStatusCard(queue_file)
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        item.setSizeHint(QSize(420, 106))
        self.analysis_list.addItem(item)
        self.analysis_list.setItemWidget(item, card)
        self._analysis_cards[path] = card

    def _update_inspector_from_result(self) -> None:
        selected = self.results_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        self.detail_status_chip.setText("결과 선택")
        self.detail_status_chip.set_tone("warning")
        self.detail_labels["영상"].setText(self._table_text(row, 4, fallback="-", user_role=True))
        self.detail_labels["구간"].setText(self._table_text(row, 2))
        self.detail_labels["타임코드"].setText(self._table_text(row, 3))
        self.detail_labels["위험도"].setText("-")
        self.detail_labels["OCR"].setText("연결 대기")
        self.detail_labels["검수"].setText(self._table_text(row, 5))
        self.evidence_text.setPlainText(self._table_text(row, 4))
        self.capture_placeholder.setText("캡처 생성 대기")

    def _table_text(self, row: int, column: int, *, fallback: str = "-", user_role: bool = False) -> str:
        item = self.results_table.item(row, column)
        if item is None:
            return fallback
        if user_role:
            value = item.data(Qt.ItemDataRole.UserRole)
            return str(value) if value else fallback
        return item.text() or fallback

    def _on_queue_selection_changed(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        path_text = current.data(Qt.ItemDataRole.UserRole)
        if not path_text:
            return
        path = Path(path_text)
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
        self.evidence_text.setPlainText(str(queue_file.path))
        self.capture_placeholder.setText("영상 등록됨")

    def _clear_inspector(self) -> None:
        self.detail_status_chip.setText("선택 없음")
        self.detail_status_chip.set_tone("neutral")
        for value in self.detail_labels.values():
            value.setText("-")
        self.evidence_text.clear()
        self.capture_placeholder.setText("캡처 프레임")

    def _refresh_header(self) -> None:
        count = len(self._queued_files)
        self.queue_count_chip.setText(f"{count}개")
        self.queue_count_chip.set_tone("success" if count else "neutral")

    def _log(self, message: str) -> None:
        self.log.appendPlainText(message)
