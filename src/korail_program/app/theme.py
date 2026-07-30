"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Pretendard GOV Variable", "Pretendard GOV", "Pretendard Variable", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #1d1d1f;
}

QMainWindow, QWidget {
    background: #f4f5f7;
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
    background: #eaecf0;
    border: none;
}

QFrame#Timeline,
QFrame#MetricCard,
QLabel#Panel {
    background: #f4f5f7;
    border: none;
    border-radius: 8px;
}

QFrame#Divider {
    background: #d8dde5;
    border: none;
    min-height: 1px;
    max-height: 1px;
}

QFrame#QueueCard {
    background: #f8f9fb;
    border: none;
    border-radius: 8px;
}

QFrame#Bubble {
    background: #f8f9fb;
    border: none;
    border-radius: 8px;
}

QLabel#Title {
    font-size: 20px;
    font-weight: 700;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
}

QLabel#Muted {
    color: #6b7280;
}

QLabel#Tiny {
    color: #6b7280;
    font-size: 11px;
}

QPushButton {
    background: #eaecf0;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #dde1e7;
}

QPushButton:pressed {
    background: #d2d7df;
}

QPushButton:disabled {
    background: #e5e7eb;
    color: #9a9a9a;
}

QPushButton#DangerButton {
    background: #f8d7da;
    color: #842029;
}

QPushButton#MainActionButton {
    background: #e1e6ee;
    min-height: 36px;
}

QToolButton#IconButton {
    background: #eaecf0;
    border: none;
    border-radius: 6px;
    min-width: 40px;
    min-height: 40px;
}

QToolButton#IconButton:hover {
    background: #dde1e7;
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
    background: #f4f5f7;
}

QListWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f4f5f7;
    border: none;
    border-radius: 6px;
    selection-background-color: #e1e6ee;
    selection-color: #1d1d1f;
}

QListWidget#QueueList,
QListWidget#TimelineList {
    background: transparent;
}

QListWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background: #eaecf0;
    border: none;
    padding: 8px;
    font-weight: 700;
}

QTableWidget {
    background: #ffffff;
    border: none;
    border-radius: 6px;
    gridline-color: #ededed;
    selection-background-color: #e1e6ee;
    selection-color: #1d1d1f;
}

QProgressBar {
    background: #eaecf0;
    border: none;
    border-radius: 6px;
    text-align: center;
    height: 18px;
}

QProgressBar::chunk {
    background: #5f6673;
    border-radius: 5px;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: #eaecf0;
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
    "neutral": ("#e5e7eb", "#4b5563", "#e5e7eb"),
    "success": ("#dff3e8", "#0f5132", "#dff3e8"),
    "warning": ("#fff0cc", "#7a4f00", "#fff0cc"),
    "error": ("#f8d7da", "#842029", "#f8d7da"),
}
