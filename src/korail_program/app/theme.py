"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #222222;
}

QMainWindow, QWidget {
    background: #f5f5f5;
}

QFrame#AppBar,
QFrame#Panel,
QFrame#Timeline,
QFrame#Inspector,
QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #dedede;
    border-radius: 8px;
}

QFrame#LeftRail {
    background: #ececec;
    border: none;
}

QFrame#QueueCard {
    background: #ffffff;
    border: 1px solid #dcdcdc;
    border-radius: 8px;
}

QFrame#Bubble {
    background: #f7f7f7;
    border: 1px solid #e0e0e0;
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
    background: #ffffff;
    border: 1px solid #d2d2d2;
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
    background: #eeeeee;
    color: #9a9a9a;
}

QPushButton#DangerButton {
    color: #842029;
    border-color: #e4b8bf;
}

QListWidget, QTableWidget, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #ffffff;
    border: 1px solid #d9d9d9;
    border-radius: 6px;
    selection-background-color: #e8e8e8;
    selection-color: #222222;
}

QListWidget::item {
    padding: 4px;
}

QHeaderView::section {
    background: #f0f0f0;
    border: none;
    border-bottom: 1px solid #d8d8d8;
    padding: 8px;
    font-weight: 700;
}

QTableWidget {
    gridline-color: #ededed;
}

QProgressBar {
    background: #eeeeee;
    border: 1px solid #d7d7d7;
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
    background: #f5f5f5;
    border: 1px solid #dedede;
    padding: 8px 14px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background: #ffffff;
    border-bottom-color: #ffffff;
}
"""


STATUS_COLORS = {
    "neutral": ("#f2f2f2", "#555555", "#d9d9d9"),
    "success": ("#e9f7ef", "#0f5132", "#badbcc"),
    "warning": ("#fff4de", "#8a5a00", "#ffd98a"),
    "error": ("#f8d7da", "#842029", "#f1aeb5"),
}
