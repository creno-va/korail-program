"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Pretendard GOV", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1f2328;
    letter-spacing: 0px;
}

QMainWindow,
QWidget {
    background: #f5f6f8;
}

QLabel {
    background: transparent;
}

QFrame#Panel,
QFrame#Inspector,
QFrame#TextPanel,
QLabel#CaptureBox {
    background: #ffffff;
    border: none;
    border-radius: 8px;
}

QFrame#LeftRail {
    background: #f5f6f8;
    border: none;
}

QFrame#MetricCard,
QFrame#EmptyState {
    background: #f0f2f5;
    border: none;
    border-radius: 8px;
}

QFrame#Divider {
    background: #dfe3e8;
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QFrame#QueueCard,
QFrame#StatusRow,
QFrame#EventCard {
    background: #ffffff;
    border: none;
    border-radius: 8px;
}

QFrame#SelectableCard {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 0px;
}

QFrame#SelectableCard:hover {
    background: #eceff3;
}

QFrame#SelectableCard[selected="true"] {
    background: #e6e9ee;
}

QSplitter#WorkspaceSplitter::handle {
    background: #dfe3e8;
    margin: 8px 10px;
    width: 1px;
}

QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 700;
}

QLabel#CardTitle {
    font-weight: 700;
}

QLabel#Muted {
    color: #6c737f;
}

QLabel#Tiny {
    color: #6c737f;
    font-size: 11px;
}

QLabel#PanelText {
    color: #343941;
    line-height: 145%;
}

QLabel#ButtonText {
    font-weight: 700;
}

QFrame#ActionButton {
    background: #e9edf2;
    border: none;
    border-radius: 7px;
}

QFrame#ActionButton:hover {
    background: #dfe4ea;
}

QFrame#ActionButton[tone="success"] {
    background: #dff3e8;
}

QFrame#ActionButton[tone="warning"] {
    background: #fff0cc;
}

QFrame#ActionButton[tone="error"] {
    background: #f8d7da;
}

QFrame#ActionButton[disabled="true"] {
    background: #eff1f4;
}

QFrame#ActionButton[disabled="true"] QLabel {
    color: #9aa1aa;
}

QFrame#CardList {
    background: transparent;
    border: none;
}

QWidget#CardListContent {
    background: transparent;
}

QScrollArea#CardScroll {
    background: transparent;
    border: none;
}

QScrollArea#CardScroll > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #c9ced6;
    border-radius: 4px;
    min-height: 32px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    border: none;
    height: 0px;
}

QFrame#ProgressTrackBar {
    background: #e3e7ed;
    border: none;
    border-radius: 4px;
}

QFrame#ProgressTrackChunk {
    background: #9aa3af;
    border: none;
    border-radius: 4px;
}
"""


STATUS_COLORS = {
    "neutral": ("#eef1f5", "#5f6672", "#eef1f5"),
    "success": ("#dff3e8", "#0f5132", "#dff3e8"),
    "warning": ("#fff0cc", "#7a4f00", "#fff0cc"),
    "error": ("#f8d7da", "#842029", "#f8d7da"),
}
