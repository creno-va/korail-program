"""Custom desktop widgets for the analyzer shell."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from korail_program.app.icons import material_icon
from korail_program.app.theme import STATUS_COLORS
from korail_program.core.models import RiskLevel
from korail_program.core.timecode import format_timecode


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


class ActionButton(QFrame):
    clicked = Signal()

    def __init__(
        self,
        text: str = "",
        *,
        icon_name: str | None = None,
        tone: str = "neutral",
        compact: bool = False,
    ) -> None:
        super().__init__()
        self._enabled = True
        self._tone = tone
        self._icon_label: QLabel | None = None
        self._text_label = QLabel(text)
        self._text_label.setObjectName("ButtonText")
        self.setObjectName("ActionButton")
        self.setProperty("tone", tone)
        self.setProperty("compact", compact)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(40)
        if compact:
            self.setFixedWidth(42)
        self._build_ui(icon_name=icon_name, compact=compact)

    def _build_ui(self, *, icon_name: str | None, compact: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12 if not compact else 10, 0, 12 if not compact else 10, 0)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon_name:
            self._icon_label = QLabel()
            self._icon_label.setFixedSize(18, 18)
            self.set_icon(icon_name)
            layout.addWidget(self._icon_label)
        if not compact:
            layout.addWidget(self._text_label)

    def setText(self, text: str) -> None:  # noqa: N802
        self._text_label.setText(text)

    def set_icon(self, icon_name: str) -> None:
        if self._icon_label is None:
            return
        self._icon_label.setPixmap(material_icon(icon_name).pixmap(QSize(18, 18)))

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802
        self._enabled = enabled
        super().setEnabled(enabled)
        self.setProperty("disabled", not enabled)
        self.setCursor(
            QCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._enabled and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TextPanel(QFrame):
    def __init__(self, placeholder: str = "", *, max_lines: int = 80) -> None:
        super().__init__()
        self._max_lines = max_lines
        self._lines: list[str] = []
        self.label = QLabel(placeholder)
        self.label.setObjectName("PanelText")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setObjectName("TextPanel")

        self.scroll = QScrollArea()
        self.scroll.setObjectName("TextPanelScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("TextPanelContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.label)
        content_layout.addStretch(1)
        self.scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(self.scroll)

    def set_text(self, text: str) -> None:
        self._lines = text.splitlines() or [text]
        self._refresh()

    def append(self, text: str) -> None:
        self._lines.extend(line for line in text.splitlines() if line.strip())
        if len(self._lines) > self._max_lines:
            self._lines = self._lines[-self._max_lines :]
        self._refresh()

    def clear(self) -> None:
        self._lines.clear()
        self.label.clear()

    def _refresh(self) -> None:
        self.label.setText("\n".join(self._lines))
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())


class _ProgressBarFrame(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self._value = 0
        self.setObjectName("ProgressTrackBar")
        self.setFixedHeight(8)
        self.chunk = QFrame(self)
        self.chunk.setObjectName("ProgressTrackChunk")
        self.chunk.setProperty("tone", "neutral")

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, value))
        self._sync_chunk()

    def set_tone(self, tone: str) -> None:
        self.chunk.setProperty("tone", tone)
        self.chunk.style().unpolish(self.chunk)
        self.chunk.style().polish(self.chunk)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_chunk()

    def _sync_chunk(self) -> None:
        width = int(self.width() * (self._value / 100))
        self.chunk.setGeometry(0, 0, width, self.height())


class ProgressTrack(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._value = 0
        self.track = _ProgressBarFrame()
        self.label = QLabel("0%")
        self.label.setObjectName("Tiny")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.track, stretch=1)
        layout.addWidget(self.label)

    def setValue(self, value: int) -> None:  # noqa: N802
        self._value = max(0, min(100, value))
        self.track.set_value(self._value)
        self.label.setText(f"{self._value}%")

    def set_tone(self, tone: str) -> None:
        self.track.set_tone(tone)
        self.label.setProperty("tone", tone)
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)

    def value(self) -> int:
        return self._value


class QueueCard(QFrame):
    remove_requested = Signal()

    def __init__(self, queue_file: QueueFile) -> None:
        super().__init__()
        self.queue_file = queue_file
        self.status_chip = StatusChip(queue_file.status, "neutral")
        self.remove_button = ActionButton("", icon_name="trash-can-outline", compact=True)
        self.remove_button.setToolTip("목록에서 제거")
        self.setObjectName("QueueCard")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        name = QLabel(self.queue_file.display_name)
        name.setObjectName("CardTitle")
        name.setWordWrap(True)
        top.addWidget(name, stretch=1)
        top.addWidget(self.status_chip)
        top.addWidget(self.remove_button)
        self.remove_button.clicked.connect(self.remove_requested.emit)

        meta = QLabel(f"{self.queue_file.size_label} / {self.queue_file.path.suffix.lower()}")
        meta.setObjectName("Tiny")
        meta.setWordWrap(True)

        layout.addLayout(top)
        layout.addWidget(meta)

    def set_status(self, status: str, tone: str) -> None:
        self.status_chip.setText(status)
        self.status_chip.set_tone(tone)


class AnalysisStatusCard(QFrame):
    start_requested = Signal()
    stop_requested = Signal()
    remove_requested = Signal()

    def __init__(self, queue_file: QueueFile) -> None:
        super().__init__()
        self.queue_file = queue_file
        self._run_mode = "start"
        self.status_chip = StatusChip("대기", "neutral")
        self.stage_label = QLabel("분석 대기")
        self.stage_label.setObjectName("Muted")
        self.progress = ProgressTrack()
        self._start_tooltip = "이 영상 분석 시작"
        self.run_button = ActionButton("시작", icon_name="play-circle-outline")
        self.run_button.setToolTip(self._start_tooltip)
        self.remove_button = ActionButton("", icon_name="trash-can-outline", compact=True)
        self.remove_button.setToolTip("목록에서 제거")
        self.setObjectName("StatusRow")
        self._build_ui()
        self.set_idle()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel(self.queue_file.display_name)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        top.addWidget(title, stretch=1)
        top.addWidget(self.status_chip)
        top.addWidget(self.run_button)
        top.addWidget(self.remove_button)
        self.run_button.clicked.connect(self._run_requested)
        self.remove_button.clicked.connect(self.remove_requested.emit)

        meta = QHBoxLayout()
        meta.addWidget(self.stage_label, stretch=1)
        size_label = QLabel(self.queue_file.size_label)
        size_label.setObjectName("Tiny")
        meta.addWidget(size_label)

        layout.addLayout(top)
        layout.addLayout(meta)
        layout.addWidget(self.progress)

    def set_state(self, status: str, tone: str, stage: str, progress: int) -> None:
        self.status_chip.setText(status)
        self.status_chip.set_tone(tone)
        self.stage_label.setText(stage)
        self.progress.setValue(progress)
        self.progress.set_tone(tone)

    def set_idle(self) -> None:
        self._run_mode = "start"
        self._start_tooltip = "이 영상 분석 시작"
        self.run_button.setText("시작")
        self.run_button.set_icon("play-circle-outline")
        self.run_button.setToolTip(self._start_tooltip)
        self.run_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def set_preparing(self) -> None:
        self._run_mode = "start"
        self._start_tooltip = "분석 준비 중"
        self.run_button.setText("준비")
        self.run_button.set_icon("progress-clock")
        self.run_button.setToolTip(self._start_tooltip)
        self.run_button.setEnabled(False)
        self.remove_button.setEnabled(False)

    def set_running(self) -> None:
        self._run_mode = "stop"
        self.run_button.setText("중지")
        self.run_button.set_icon("stop-circle-outline")
        self.run_button.setToolTip("이 영상 분석 중지")
        self.run_button.setEnabled(True)
        self.remove_button.setEnabled(False)

    def set_stopping(self) -> None:
        self.run_button.setText("중지 중")
        self.run_button.setEnabled(False)
        self.remove_button.setEnabled(False)

    def set_finished(self) -> None:
        self._run_mode = "start"
        self._start_tooltip = "이 영상 다시 분석"
        self.run_button.setText("다시")
        self.run_button.set_icon("replay")
        self.run_button.setToolTip(self._start_tooltip)
        self.run_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def set_start_available(self, enabled: bool, *, disabled_reason: str) -> None:
        if self._run_mode != "start":
            return
        self.run_button.setEnabled(enabled)
        self.run_button.setToolTip(self._start_tooltip if enabled else disabled_reason)

    def _run_requested(self) -> None:
        if self._run_mode == "stop":
            self.stop_requested.emit()
            return
        self.start_requested.emit()


class EventCard(QFrame):
    def __init__(self, event_payload: dict[str, Any], *, video_name: str) -> None:
        super().__init__()
        self.payload = event_payload
        self.setObjectName("EventCard")
        self._build_ui(video_name=video_name)

    def _build_ui(self, *, video_name: str) -> None:
        risk = RiskLevel.coerce(self.payload.get("risk_level"))
        start_ms = int(self.payload.get("start_time_ms", 0))
        end_ms = int(self.payload.get("end_time_ms", 0))
        section = f"{self.payload.get('section_start', '구간 미확인')} ~ {self.payload.get('section_end', '구간 미확인')}"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)

        top = QHBoxLayout()
        title = QLabel(video_name)
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        top.addWidget(title, stretch=1)
        top.addWidget(StatusChip(risk.value, _tone_for_risk(risk)))

        meta = QLabel(f"{format_timecode(start_ms)} - {format_timecode(end_ms)} / {section}")
        meta.setObjectName("Tiny")
        meta.setWordWrap(True)

        summary = QLabel(str(self.payload.get("summary", "지장수목 의심 이벤트")))
        summary.setObjectName("PanelText")
        summary.setWordWrap(True)

        layout.addLayout(top)
        layout.addWidget(meta)
        layout.addWidget(summary)


class EmptyState(QFrame):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.setObjectName("EmptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 22)
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("Muted")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

    def set_text(self, text: str) -> None:
        self.label.setText(text)


class _SelectableCard(QFrame):
    clicked = Signal(object)

    def __init__(self, key: object, child: QWidget) -> None:
        super().__init__()
        self.key = key
        self.setObjectName("SelectableCard")
        self.setProperty("selected", False)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(child)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CardList(QFrame):
    files_dropped = Signal(list)
    selection_changed = Signal(object)
    selection_set_changed = Signal(list)

    def __init__(
        self,
        empty_text: str,
        *,
        accept_drops: bool = False,
        multi_select: bool = False,
    ) -> None:
        super().__init__()
        self._empty_text = empty_text
        self._multi_select = multi_select
        self._items: dict[object, QWidget] = {}
        self._wrappers: dict[object, _SelectableCard] = {}
        self._card_count = 0
        self._selected_key: object | None = None
        self._selected_keys: set[object] = set()
        self.setObjectName("CardList")
        self.setAcceptDrops(accept_drops)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("CardScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.content.setObjectName("CardListContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)
        self.set_empty()

    def clear_cards(self) -> None:
        self._selected_key = None
        self._selected_keys.clear()
        self._items.clear()
        self._wrappers.clear()
        self._card_count = 0
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.content_layout.addStretch(1)
        self._empty = None
        self.set_empty()

    def add_card(self, key: object, card: QWidget, *, selectable: bool = True) -> None:
        self._remove_empty()
        wrapper = _SelectableCard(key, card) if selectable else card
        if isinstance(wrapper, _SelectableCard):
            wrapper.clicked.connect(lambda item_key: self._select(item_key, toggle=True))
            self._wrappers[key] = wrapper
        self._items[key] = wrapper
        self._card_count += 1
        self.content_layout.insertWidget(self.content_layout.count() - 1, wrapper)

    def remove_card(self, key: object) -> None:
        widget = self._items.pop(key, None)
        self._wrappers.pop(key, None)
        if widget is None:
            return
        self.content_layout.removeWidget(widget)
        widget.setParent(None)
        widget.deleteLater()
        self._card_count = max(0, self._card_count - 1)
        was_selected = key in self._selected_keys
        self._selected_keys.discard(key)
        if self._selected_key == key:
            self._selected_key = next(iter(self._selected_keys), None)
        if not self._card_count:
            self.set_empty()
        if was_selected:
            self.selection_set_changed.emit(list(self._selected_keys))

    def set_empty(self) -> None:
        if self._card_count:
            return
        self._remove_empty()
        self._empty = EmptyState(self._empty_text)
        self.content_layout.insertWidget(0, self._empty)

    def set_empty_text(self, text: str) -> None:
        self._empty_text = text
        empty = getattr(self, "_empty", None)
        if empty is not None:
            empty.set_text(text)

    def select_key(self, key: object) -> None:
        if key in self._wrappers:
            self._select(key, toggle=False)

    def selected_keys(self) -> list[object]:
        return list(self._selected_keys)

    def _select(self, key: object, *, toggle: bool) -> None:
        if self._multi_select:
            if toggle and key in self._selected_keys:
                self._selected_keys.remove(key)
                if self._selected_key == key:
                    self._selected_key = next(iter(self._selected_keys), None)
            else:
                self._selected_keys.add(key)
                self._selected_key = key
        else:
            self._selected_keys = {key}
            self._selected_key = key
        for item_key, wrapper in self._wrappers.items():
            wrapper.set_selected(item_key in self._selected_keys)
        self.selection_changed.emit(key)
        self.selection_set_changed.emit(list(self._selected_keys))

    def _remove_empty(self) -> None:
        empty = getattr(self, "_empty", None)
        if empty is None:
            return
        empty.setParent(None)
        empty.deleteLater()
        self._empty = None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self.acceptDrops() and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self.acceptDrops() and event.mimeData().hasUrls():
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
    line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return line


def _tone_for_risk(risk: RiskLevel) -> str:
    if risk is RiskLevel.HIGH:
        return "error"
    if risk is RiskLevel.MEDIUM:
        return "warning"
    if risk is RiskLevel.LOW:
        return "success"
    return "neutral"
