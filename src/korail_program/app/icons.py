"""Material Design icon helpers."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QLabel

ICON_COLOR = "#31343a"
ICON_MUTED = "#6b7280"
ICON_SUCCESS = "#0f5132"
ICON_WARNING = "#7a4f00"
ICON_ERROR = "#842029"

_MATERIAL_FONT_FAMILY: str | None = None
_MATERIAL_CHARMAP: dict[str, str] | None = None


def material_icon(name: str, *, color: str = ICON_COLOR) -> QIcon:
    """Return a Material Design Icon rendered from the bundled MDI font."""

    charmap = _load_material_charmap()
    family = _load_material_font()
    codepoint = charmap.get(name) if charmap else None
    if family is None or codepoint is None:
        return QIcon()

    icon = QIcon()
    glyph = chr(int(codepoint, 16))
    for size in (16, 18, 20, 24, 32, 48):
        icon.addPixmap(_render_icon_pixmap(glyph, family=family, color=color, size=size))
    return icon


def icon_label(name: str, *, color: str = ICON_MUTED, size: int = 18) -> QLabel:
    label = QLabel()
    pixmap = material_icon(name, color=color).pixmap(QSize(size, size))
    label.setPixmap(pixmap)
    label.setFixedSize(size, size)
    return label


def _load_material_font() -> str | None:
    global _MATERIAL_FONT_FAMILY
    if _MATERIAL_FONT_FAMILY is not None:
        return _MATERIAL_FONT_FAMILY

    fonts_dir = _qtawesome_fonts_dir()
    if fonts_dir is None:
        return None
    font_path = fonts_dir / "materialdesignicons6-webfont-6.9.96.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        return None
    families = QFontDatabase.applicationFontFamilies(font_id)
    _MATERIAL_FONT_FAMILY = families[0] if families else None
    return _MATERIAL_FONT_FAMILY


def _load_material_charmap() -> dict[str, str]:
    global _MATERIAL_CHARMAP
    if _MATERIAL_CHARMAP is not None:
        return _MATERIAL_CHARMAP

    fonts_dir = _qtawesome_fonts_dir()
    if fonts_dir is None:
        _MATERIAL_CHARMAP = {}
        return _MATERIAL_CHARMAP
    charmap_path = fonts_dir / "materialdesignicons6-webfont-charmap-6.9.96.json"
    _MATERIAL_CHARMAP = json.loads(charmap_path.read_text(encoding="utf-8"))
    return _MATERIAL_CHARMAP


def _qtawesome_fonts_dir() -> Path | None:
    try:
        import qtawesome
    except ImportError:
        return None
    return Path(qtawesome.__file__).parent / "fonts"


def _render_icon_pixmap(glyph: str, *, family: str, color: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setPen(QColor(color))

    font = QFont(family)
    font.setPixelSize(size)
    painter.setFont(font)
    painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    return pixmap
