"""Light desktop theme for the PySide6 app."""

from __future__ import annotations

APP_STYLESHEET = """
* {
    font-family: "Pretendard GOV", "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #191f28;
    letter-spacing: 0px;
}

QMainWindow,
QWidget {
    background: #f9fafb;
}

QLabel {
    background: transparent;
}

QFrame#WorkPanel,
QFrame#TextPanel {
    background: #ffffff;
    border: none;
    border-radius: 0px;
}

QFrame#LeftRail {
    background: #f2f4f6;
    border: none;
}

QFrame#ResultsRail {
    background: #f2f4f6;
    border: none;
}

QFrame#EmptyState {
    background: #ffffff;
    border: none;
    border-radius: 12px;
}

QFrame#ModelCard,
QFrame#SidebarSettings {
    background: #ffffff;
    border: none;
    border-radius: 12px;
}

QFrame#StatisticsPanel {
    background: #ffffff;
    border: none;
    border-radius: 14px;
}

QFrame#StatTile {
    background: transparent;
    border: none;
    border-radius: 0px;
}

QFrame#AnalysisBlock {
    background: #f2f4f6;
    border: none;
    border-radius: 14px;
}

QFrame#DetailBlock {
    background: #f9fafb;
    border: none;
    border-radius: 14px;
}

QFrame#FlatSection,
QWidget#WorkScrollContent,
QScrollArea#WorkScroll,
QScrollArea#WorkScroll > QWidget > QWidget {
    background: #ffffff;
    border: none;
}

QLabel#StatValue {
    font-size: 22px;
    font-weight: 700;
    color: #191f28;
}

QFrame#StatusRow,
QFrame#EventCard {
    background: transparent;
    border: none;
    border-radius: 12px;
}

QFrame#EventCard {
    background: #ffffff;
}

QDialog {
    background: #f9fafb;
}

QFrame#SelectableCard {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 0px;
}

QFrame#SelectableCard:hover {
    background: #e5e8eb;
}

QFrame#SelectableCard[selected="true"] {
    background: #dfe3e8;
}

QSplitter#WorkspaceSplitter::handle {
    background: #d1d6db;
    margin: 0px;
    width: 1px;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
}

QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #191f28;
}

QLabel#CardTitle {
    font-weight: 700;
    color: #333d4b;
}

QLabel#Muted {
    color: #8b95a1;
    font-size: 12px;
}

QLabel#Tiny {
    color: #8b95a1;
    font-size: 12px;
}

QLabel#PanelText {
    color: #4e5968;
    line-height: 145%;
}

QLabel#ModelName {
    color: #333d4b;
    font-weight: 700;
    padding: 0px;
}

QLabel#ButtonText {
    font-size: 13px;
    font-weight: 600;
}

QLineEdit#TokenInput {
    background: #ffffff;
    border: 1px solid #e5e8eb;
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: #e8f3ff;
}

QLineEdit#TokenInput:focus {
    border: 1px solid #3182f6;
}

QFrame#ActionButton {
    background: #e5e8eb;
    border: none;
    border-radius: 10px;
}

QFrame#ActionButton:hover {
    background: #d1d6db;
}

QFrame#ActionButton[compact="true"] {
    background: transparent;
}

QFrame#ActionButton[compact="true"]:hover {
    background: #d1d6db;
}

QFrame#ActionButton[tone="primary"],
QFrame#ActionButton[tone="success"] {
    background: #3182f6;
}

QFrame#ActionButton[tone="primary"]:hover,
QFrame#ActionButton[tone="success"]:hover {
    background: #1b64da;
}

QFrame#ActionButton[tone="primary"] QLabel,
QFrame#ActionButton[tone="success"] QLabel,
QFrame#ActionButton[tone="error"] QLabel {
    color: #ffffff;
}

QFrame#ActionButton[tone="warning"] {
    background: #fff4e5;
}

QFrame#ActionButton[tone="error"] {
    background: #f04452;
}

QFrame#ActionButton[tone="error"]:hover {
    background: #d33b4c;
}

QFrame#ActionButton[disabled="true"] {
    background: #f2f4f6;
}

QFrame#ActionButton[disabled="true"] QLabel {
    color: #8b95a1;
}

QFrame#CardList {
    background: transparent;
    border: none;
}

QScrollArea#TextPanelScroll,
QWidget#TextPanelContent {
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
    background: #b0b8c1;
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
    background: #dfe3e8;
    border: none;
    border-radius: 4px;
}

QFrame#ProgressTrackChunk {
    background: #8b95a1;
    border: none;
    border-radius: 4px;
}

QFrame#ProgressTrackChunk[tone="primary"],
QFrame#ProgressTrackChunk[tone="success"] {
    background: #3182f6;
}

QFrame#VideoPlayer {
    background: #ffffff;
    border: none;
}

QFrame#VideoSurfaceFrame,
QFrame#VideoDisplay,
QVideoWidget#VideoSurface,
QLabel#VideoPlaceholder {
    background: #17191c;
    color: #b0b8c1;
    border: none;
    border-radius: 16px;
}

QFrame#VideoControlsOverlay {
    background: rgba(17, 19, 22, 220);
    border: none;
    border-radius: 10px;
    margin: 0px 12px 12px 12px;
}

QFrame#VideoControlsOverlay QFrame#ActionButton {
    background: transparent;
}

QFrame#VideoControlsOverlay QFrame#ActionButton:hover {
    background: rgba(255, 255, 255, 28);
}

QFrame#VideoControlsOverlay QLabel#ButtonText,
QLabel#VideoTimeLabel {
    color: #ffffff;
}

QLabel#FrameThumbnail {
    background: #e5e8eb;
    color: #8b95a1;
    border: none;
    border-radius: 10px;
    font-size: 12px;
}

QSlider#VideoSeekSlider {
    background: transparent;
    min-height: 12px;
    max-height: 12px;
}

QSlider#VideoSeekSlider::groove:horizontal {
    height: 5px;
    background: #d1d6db;
    border-radius: 2px;
}

QFrame#VideoControlsOverlay QSlider#VideoSeekSlider::groove:horizontal {
    height: 3px;
    background: rgba(255, 255, 255, 95);
    border-radius: 1px;
}

QSlider#VideoSeekSlider::sub-page:horizontal {
    background: #3182f6;
    border-radius: 2px;
}

QSlider#VideoSeekSlider::handle:horizontal {
    background: #3182f6;
    width: 10px;
    margin: -4px 0;
    border-radius: 5px;
}

QFrame#ProgressTrackChunk[tone="warning"] {
    background: #f59f00;
}

QFrame#ProgressTrackChunk[tone="error"] {
    background: #f04452;
}

QLabel#Tiny[tone="success"] {
    color: #008f6a;
}

QLabel#Tiny[tone="primary"] {
    color: #1b64da;
}

QLabel#Tiny[tone="warning"] {
    color: #b25d00;
}

QLabel#Tiny[tone="error"] {
    color: #d33b4c;
}
"""


STATUS_COLORS = {
    "neutral": ("#f2f4f6", "#6b7684", "#f2f4f6"),
    "primary": ("#e8f3ff", "#1b64da", "#e8f3ff"),
    "success": ("#e8f8f2", "#008f6a", "#e8f8f2"),
    "warning": ("#fff4e5", "#b25d00", "#fff4e5"),
    "error": ("#feecef", "#d33b4c", "#feecef"),
}
