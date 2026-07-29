"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #222222;
}

QMainWindow, QWidget {
    background: #eeeeee;
}

QFrame#Panel,
QFrame#Inspector {
    background: #ffffff;
    border: none;
    border-radius: 10px;
}

QFrame#LeftRail {
    background: #e6e6e6;
    border: none;
}

QFrame#Timeline,
QFrame#MetricCard,
QLabel#Panel {
    background: #f3f3f3;
    border: none;
    border-radius: 10px;
}

QFrame#QueueCard {
    background: #f7f7f7;
    border: none;
    border-radius: 8px;
}

QFrame#Bubble {
    background: #f3f3f3;
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
    color: #737373;
}

QLabel#Tiny {
    color: #737373;
    font-size: 11px;
}

QPushButton {
    background: #e9e9e9;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
}

QPushButton:hover {
    background: #f0f0f0;
}

QPushButton:pressed {
    background: #e6e6e6;
}

QPushButton:disabled {
    background: #dedede;
    color: #9a9a9a;
}

QPushButton#DangerButton {
    background: #f8d7da;
    color: #842029;
}

QListWidget, QTableWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #f3f3f3;
    border: none;
    border-radius: 6px;
    selection-background-color: #e8e8e8;
    selection-color: #222222;
}

QListWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background: #e9e9e9;
    border: none;
    padding: 8px;
    font-weight: 700;
}

QTableWidget {
    gridline-color: #ededed;
}

QProgressBar {
    background: #e3e3e3;
    border: none;
    border-radius: 6px;
    text-align: center;
    height: 18px;
}

QProgressBar::chunk {
    background: #6f6f6f;
    border-radius: 5px;
}

QTabWidget::pane {
    border: none;
}

QTabBar::tab {
    background: #e9e9e9;
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
    "neutral": ("#e5e5e5", "#555555", "#e5e5e5"),
    "success": ("#dff3e8", "#0f5132", "#dff3e8"),
    "warning": ("#fff0cc", "#7a4f00", "#fff0cc"),
    "error": ("#f8d7da", "#842029", "#f8d7da"),
}
