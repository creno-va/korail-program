"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Pretendard GOV", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #202124;
}

QMainWindow, QWidget {
    background: #f7f7f8;
}

QLabel {
    background: transparent;
}

QFrame#Panel,
QFrame#Inspector {
    background: #ffffff;
    border: none;
    border-radius: 8px;
}

QFrame#LeftRail {
    background: #f7f7f8;
    border: none;
}

QFrame#MetricCard,
QLabel#CaptureBox {
    background: #f7f7f8;
    border: none;
    border-radius: 8px;
}

QFrame#Divider {
    background: #e6e7eb;
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QFrame#QueueCard {
    background: #ffffff;
    border: none;
    border-radius: 8px;
}

QFrame#StatusRow {
    background: #ffffff;
    border: none;
    border-radius: 8px;
}

QSplitter#WorkspaceSplitter::handle {
    background: #e6e7eb;
    margin: 8px 10px;
    width: 1px;
}

QLabel#Title {
    font-size: 20px;
    font-weight: 700;
}

QLabel#SectionTitle {
    font-size: 14px;
    font-weight: 700;
}

QLabel#Muted {
    color: #70757a;
}

QLabel#Tiny {
    color: #70757a;
    font-size: 11px;
}

QPushButton {
    background: #f1f2f4;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #e8eaed;
}

QPushButton:pressed {
    background: #dfe1e5;
}

QPushButton:disabled {
    background: #f1f2f4;
    color: #9a9a9a;
}

QPushButton#DangerButton {
    background: #f8d7da;
    color: #842029;
}

QPushButton#MainActionButton {
    background: #e8eaed;
    min-height: 36px;
}

QToolButton#IconButton {
    background: #f1f2f4;
    border: none;
    border-radius: 6px;
    min-width: 40px;
    min-height: 40px;
}

QToolButton#IconButton:hover {
    background: #e8eaed;
}

QMenu {
    background: #ffffff;
    border: none;
    padding: 6px;
}

QMenu::item {
    padding: 8px 28px 8px 12px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: #f1f2f4;
}

QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f7f7f8;
    border: none;
    border-radius: 6px;
    selection-background-color: #e8eaed;
    selection-color: #202124;
}

QListWidget#QueueList,
QListWidget#AnalysisList {
    background: transparent;
}

QListWidget::item {
    padding: 4px;
}

QListWidget::item:selected,
QListWidget::item:hover {
    background: transparent;
}

QListWidget::item:focus {
    outline: none;
}

QHeaderView::section {
    background: #f1f2f4;
    border: none;
    padding: 8px;
    font-weight: 700;
}

QTableWidget {
    background: #ffffff;
    border: none;
    border-radius: 6px;
    gridline-color: #eef0f2;
    selection-background-color: #e8eaed;
    selection-color: #202124;
}

QProgressBar {
    background: #f1f2f4;
    border: none;
    border-radius: 6px;
    text-align: center;
    height: 18px;
}

QProgressBar::chunk {
    background: #c4c7cc;
    border-radius: 5px;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: #f1f2f4;
    border: none;
    padding: 8px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #ffffff;
}
"""


STATUS_COLORS = {
    "neutral": ("#f1f2f4", "#5f6368", "#f1f2f4"),
    "success": ("#dff3e8", "#0f5132", "#dff3e8"),
    "warning": ("#fff0cc", "#7a4f00", "#fff0cc"),
    "error": ("#f8d7da", "#842029", "#f8d7da"),
}
