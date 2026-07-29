"""Main PySide6 desktop window."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
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
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.theme import APP_STYLESHEET, STATUS_COLORS
from korail_program.core.timecode import format_timecode

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


@dataclass(frozen=True, slots=True)
class QueueFile:
    path: Path
    size_bytes: int
    status: str = "대기"

    @property
    def display_name(self) -> str:
        return self.path.name

    @property
    def size_label(self) -> str:
        size_mb = self.size_bytes / (1024 * 1024)
        if size_mb >= 1024:
            return f"{size_mb / 1024:.1f} GB"
        return f"{size_mb:.1f} MB"


class StatusChip(QLabel):
    def __init__(self, text: str, tone: str = "neutral") -> None:
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(24)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        bg, fg, _ = STATUS_COLORS.get(tone, STATUS_COLORS["neutral"])
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border: none;
                border-radius: 12px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            """
        )


class QueueCard(QWidget):
    def __init__(self, queue_file: QueueFile) -> None:
        super().__init__()
        self.queue_file = queue_file
        self.status_chip = StatusChip(queue_file.status, "neutral")
        self._build_ui()

    def _build_ui(self) -> None:
        frame = QFrame()
        frame.setObjectName("QueueCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(self.queue_file.display_name)
        name.setStyleSheet("font-weight: 700;")
        name.setWordWrap(True)
        top.addWidget(name, stretch=1)
        top.addWidget(self.status_chip)

        meta = QLabel(f"{self.queue_file.size_label}  ·  {self.queue_file.path.suffix.lower()}")
        meta.setObjectName("Tiny")
        meta.setWordWrap(True)

        layout.addLayout(top)
        layout.addWidget(meta)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

    def set_status(self, status: str, tone: str) -> None:
        self.status_chip.setText(status)
        self.status_chip.set_tone(tone)


class DropQueueList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setSpacing(8)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._queued_files: dict[Path, QueueFile] = {}
        self._queue_cards: dict[Path, QueueCard] = {}
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

        self.add_files_button = QPushButton("추가")
        self.add_files_button.setIcon(_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.add_files_button.clicked.connect(self._choose_files)
        header.addWidget(self.add_files_button)

        self.queue_list = DropQueueList()
        self.queue_list.files_dropped.connect(self.add_video_files)
        self.queue_list.currentItemChanged.connect(self._on_queue_selection_changed)

        empty_hint = QLabel("mp4, avi, mov, mkv 파일을 드래그하세요.")
        empty_hint.setObjectName("Muted")
        empty_hint.setWordWrap(True)

        self.clear_button = QPushButton("대기열 비우기")
        self.clear_button.setObjectName("DangerButton")
        self.clear_button.clicked.connect(self.clear_queue)

        layout.addLayout(header)
        layout.addWidget(empty_hint)
        layout.addWidget(self.queue_list, stretch=1)
        layout.addWidget(self.clear_button)
        return panel

    def _build_work_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        action_row = QHBoxLayout()
        title = QLabel("작업 흐름")
        title.setObjectName("SectionTitle")
        action_row.addWidget(title)
        self.model_chip = StatusChip("Gemma 필요", "warning")
        self.ocr_chip = StatusChip("OCR 필요", "warning")
        action_row.addWidget(self.model_chip)
        action_row.addWidget(self.ocr_chip)
        action_row.addStretch(1)

        self.start_button = QPushButton("분석 시작")
        self.start_button.setIcon(_icon(QStyle.StandardPixmap.SP_MediaPlay))
        self.start_button.clicked.connect(self.start_analysis)
        self.export_button = QPushButton("리포트 내보내기")
        self.export_button.setIcon(_icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.export_button.clicked.connect(self.export_report)
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.export_button)

        timeline = QFrame()
        timeline.setObjectName("Timeline")
        timeline_layout = QVBoxLayout(timeline)
        timeline_layout.setContentsMargins(12, 12, 12, 12)
        timeline_layout.setSpacing(8)
        timeline_header = QHBoxLayout()
        timeline_title = QLabel("타임라인")
        timeline_title.setObjectName("SectionTitle")
        self.session_chip = StatusChip("대기 중", "neutral")
        timeline_header.addWidget(timeline_title)
        timeline_header.addStretch(1)
        timeline_header.addWidget(self.session_chip)
        self.timeline_list = QListWidget()
        self.timeline_list.setFrameShape(QFrame.Shape.NoFrame)
        self.timeline_list.setSpacing(6)
        timeline_layout.addLayout(timeline_header)
        timeline_layout.addWidget(self.timeline_list, stretch=1)

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
        layout.addWidget(timeline, stretch=2)
        layout.addLayout(result_header)
        layout.addWidget(self.results_table, stretch=3)
        layout.addWidget(self.progress)

        self._append_timeline("앱 준비 완료", "neutral", "영상 파일을 등록하면 분석 작업을 구성할 수 있습니다.")
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
        self.capture_placeholder.setObjectName("Panel")

        fields = QFrame()
        fields.setObjectName("MetricCard")
        grid = QGridLayout(fields)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.detail_labels: dict[str, QLabel] = {}
        for row, key in enumerate(["영상", "구간", "타임코드", "위험도", "OCR", "검수"]):
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
        layout.addWidget(self.capture_placeholder)
        layout.addWidget(fields)
        layout.addWidget(evidence_label)
        layout.addWidget(self.evidence_text, stretch=1)
        layout.addWidget(log_label)
        layout.addWidget(self.log)
        return panel

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(APP_STYLESHEET)

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
            added += 1

        if added:
            self._append_timeline("영상 등록", "success", f"{added}개 파일이 대기열에 추가되었습니다.")
            self._log(f"영상 {added}개 등록")
        if skipped:
            self._append_timeline("등록 제외", "warning", f"{skipped}개 파일은 중복 또는 미지원 형식입니다.")
            self._log(f"중복 또는 미지원 파일 {skipped}개 제외")
        self._refresh_header()

    def clear_queue(self) -> None:
        self._queued_files.clear()
        self._queue_cards.clear()
        self.queue_list.clear()
        self.results_table.setRowCount(0)
        self.progress.setValue(0)
        self.event_count_chip.setText("0건")
        self.event_count_chip.set_tone("neutral")
        self._clear_inspector()
        self._append_timeline("대기열 초기화", "neutral", "등록된 영상과 임시 결과를 비웠습니다.")
        self._refresh_header()

    def start_analysis(self) -> None:
        if not self._queued_files:
            self._append_timeline("분석 보류", "warning", "먼저 영상 파일을 등록하세요.")
            QMessageBox.warning(self, "영상 없음", "분석할 영상 파일을 먼저 등록하세요.")
            return

        self.results_table.setRowCount(0)
        total = len(self._queued_files)
        self.session_chip.setText("준비 점검")
        self.session_chip.set_tone("warning")
        self.progress.setValue(0)

        for index, (path, queue_file) in enumerate(self._queued_files.items(), start=1):
            card = self._queue_cards[path]
            card.set_status("점검", "warning")
            self._append_timeline(
                "분석 준비",
                "neutral",
                f"{queue_file.display_name}: 파일 확인 완료, 모델/OCR 파이프라인 연결 대기",
            )
            progress = int(index / total * 100)
            self.progress.setValue(progress)
            card.set_status("준비 완료", "success")
            self._add_preflight_result(queue_file)

        self.session_chip.setText("백엔드 연결 대기")
        self.session_chip.set_tone("warning")
        self.model_chip.setText("Gemma 연결 필요")
        self.model_chip.set_tone("warning")
        self.ocr_chip.setText("PaddleOCR 연결 필요")
        self.ocr_chip.set_tone("warning")
        self.event_count_chip.setText(f"{self.results_table.rowCount()}건")
        self.event_count_chip.set_tone("warning")
        self._append_timeline(
            "분석 워커 필요",
            "warning",
            "GUI와 대기열은 준비되었습니다. 다음 단계에서 Gemma/PaddleOCR 실행 워커를 연결합니다.",
        )

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
            self._append_timeline("리포트 대기", "warning", f"리포트 엔진 연결 후 저장 예정: {target}")

    def _add_preflight_result(self, queue_file: QueueFile) -> None:
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        values = [
            ("대기", "warning"),
            ("-", "neutral"),
            ("구간 미확인", "neutral"),
            f"{format_timecode(0)} - {format_timecode(0)}",
            "모델/OCR 연결 후 실제 지장수목 이벤트가 표시됩니다.",
            "미확인",
        ]
        status_text, status_tone = values[0]
        risk_text, risk_tone = values[1]
        self.results_table.setCellWidget(row, 0, StatusChip(status_text, status_tone))
        self.results_table.setCellWidget(row, 1, StatusChip(risk_text, risk_tone))
        for column, value in enumerate(values[2:], start=2):
            item = QTableWidgetItem(value)
            if column == 4:
                item.setData(Qt.ItemDataRole.UserRole, queue_file.display_name)
            self.results_table.setItem(row, column, item)

    def _append_timeline(self, title: str, tone: str, body: str) -> None:
        item = QListWidgetItem()
        bubble = QFrame()
        bubble.setObjectName("Bubble")
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(4)
        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 700;")
        top.addWidget(title_label)
        top.addStretch(1)
        top.addWidget(StatusChip(tone_label(tone), tone))
        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setObjectName("Muted")
        layout.addLayout(top)
        layout.addWidget(body_label)
        item.setSizeHint(QSize(420, 72))
        self.timeline_list.addItem(item)
        self.timeline_list.setItemWidget(item, bubble)
        self.timeline_list.scrollToBottom()

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


def _icon(icon: QStyle.StandardPixmap) -> QIcon:
    app = QApplication.instance()
    if app is None:
        return QIcon()
    return app.style().standardIcon(icon)


def tone_label(tone: str) -> str:
    return {
        "success": "정상",
        "warning": "주의",
        "error": "오류",
        "neutral": "상태",
    }.get(tone, "상태")
