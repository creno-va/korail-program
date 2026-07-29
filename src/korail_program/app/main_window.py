"""Main PySide6 desktop window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


class VideoQueueList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._queued_files: set[Path] = set()
        self.setWindowTitle("Korail Obstruction Analyzer")
        self.resize(1320, 840)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        toolbar = self._build_toolbar()
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_queue_panel())
        splitter.addWidget(self._build_center_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([300, 700, 320])
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._build_status_panel())
        self.setCentralWidget(root)

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        self.add_files_button = QPushButton("파일 추가")
        self.start_button = QPushButton("분석 시작")
        self.export_button = QPushButton("리포트 내보내기")
        self.settings_button = QPushButton("설정")

        self.add_files_button.clicked.connect(self._choose_files)
        self.start_button.clicked.connect(self._show_not_connected)
        self.export_button.clicked.connect(self._show_not_connected)
        self.settings_button.clicked.connect(self._show_not_connected)

        layout.addWidget(self.add_files_button)
        layout.addWidget(self.start_button)
        layout.addWidget(self.export_button)
        layout.addStretch(1)
        layout.addWidget(self.settings_button)
        return layout

    def _build_queue_panel(self) -> QWidget:
        group = QGroupBox("영상 대기열")
        layout = QVBoxLayout(group)
        hint = QLabel("드래그 앤 드롭 또는 파일 추가 버튼으로 영상을 등록")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.queue_list = VideoQueueList()
        self.queue_list.files_dropped.connect(self.add_video_files)
        layout.addWidget(self.queue_list)
        return group

    def _build_center_panel(self) -> QWidget:
        tabs = QTabWidget()

        self.results_table = QTableWidget(0, 6)
        self.results_table.setHorizontalHeaderLabels(
            ["위험도", "구간", "타임코드", "요약", "캡처", "검수"]
        )
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self.results_table, "분석 결과")

        capture_panel = QLabel("이벤트를 선택하면 캡처와 원본 프레임이 표시됩니다.")
        capture_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capture_panel.setFrameShape(QFrame.Shape.StyledPanel)
        tabs.addTab(capture_panel, "캡처 보기")

        history_panel = QLabel("분석 이력 조회 화면")
        history_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        history_panel.setFrameShape(QFrame.Shape.StyledPanel)
        tabs.addTab(history_panel, "이력")

        return tabs

    def _build_detail_panel(self) -> QWidget:
        group = QGroupBox("이벤트 상세")
        layout = QGridLayout(group)
        labels = [
            ("영상", "-"),
            ("구간", "-"),
            ("타임코드", "-"),
            ("위험도", "-"),
            ("OCR 신뢰도", "-"),
            ("검수 상태", "-"),
        ]
        for row, (name, value) in enumerate(labels):
            title = QLabel(name)
            title.setStyleSheet("font-weight: 600;")
            layout.addWidget(title, row, 0)
            layout.addWidget(QLabel(value), row, 1)

        self.evidence_text = QPlainTextEdit()
        self.evidence_text.setReadOnly(True)
        self.evidence_text.setPlaceholderText("Judge 판단 근거")
        self.evidence_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.evidence_text, len(labels), 0, 1, 2)
        return group

    def _build_status_panel(self) -> QWidget:
        group = QGroupBox("진행 상태")
        layout = QVBoxLayout(group)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.appendPlainText("대기 중")
        layout.addWidget(self.progress)
        layout.addWidget(self.log)
        return group

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
            normalized = path.resolve()
            if normalized.suffix.lower() not in VIDEO_EXTENSIONS or normalized in self._queued_files:
                skipped += 1
                continue
            self._queued_files.add(normalized)
            item = QListWidgetItem(f"{normalized.name} - 대기")
            item.setData(Qt.ItemDataRole.UserRole, str(normalized))
            self.queue_list.addItem(item)
            added += 1

        if added:
            self.log.appendPlainText(f"영상 {added}개 등록")
        if skipped:
            self.log.appendPlainText(f"중복 또는 미지원 파일 {skipped}개 제외")

    def _show_not_connected(self) -> None:
        QMessageBox.information(self, "준비 중", "분석 백엔드는 다음 구현 단계에서 연결됩니다.")
