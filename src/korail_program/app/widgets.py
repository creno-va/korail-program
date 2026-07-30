"""Reusable PySide6 widgets used by the desktop shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.theme import STATUS_COLORS


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

        meta = QLabel(f"{self.queue_file.size_label} / {self.queue_file.path.suffix.lower()}")
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


class AnalysisStatusCard(QWidget):
    def __init__(self, queue_file: QueueFile) -> None:
        super().__init__()
        self.queue_file = queue_file
        self.status_chip = StatusChip("대기", "neutral")
        self.stage_label = QLabel("분석 대기")
        self.stage_label.setObjectName("Muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._build_ui()

    def _build_ui(self) -> None:
        frame = QFrame()
        frame.setObjectName("StatusRow")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(self.queue_file.display_name)
        title.setStyleSheet("font-weight: 700;")
        title.setWordWrap(True)
        top.addWidget(title, stretch=1)
        top.addWidget(self.status_chip)

        meta = QHBoxLayout()
        meta.addWidget(self.stage_label, stretch=1)
        size_label = QLabel(self.queue_file.size_label)
        size_label.setObjectName("Tiny")
        meta.addWidget(size_label)

        layout.addLayout(top)
        layout.addLayout(meta)
        layout.addWidget(self.progress)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

    def set_state(self, status: str, tone: str, stage: str, progress: int) -> None:
        self.status_chip.setText(status)
        self.status_chip.set_tone(tone)
        self.stage_label.setText(stage)
        self.progress.setValue(max(0, min(100, progress)))


class EmptyState(QWidget):
    def __init__(self, text: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 24, 12, 24)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("Muted")
        label.setWordWrap(True)
        layout.addWidget(label)


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


def horizontal_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line
