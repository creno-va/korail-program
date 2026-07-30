"""Application font loading."""

from __future__ import annotations

from importlib import resources

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

FONT_FAMILIES = [
    "Pretendard GOV",
    "Pretendard",
    "Malgun Gothic",
    "Segoe UI",
]


def configure_app_font(app: QApplication) -> None:
    """Load bundled Pretendard GOV and set the application font stack."""

    _load_bundled_pretendard_gov()
    for family in FONT_FAMILIES:
        if family in QFontDatabase.families():
            app.setFont(QFont(family, 9))
            return
    app.setFont(QFont("Malgun Gothic", 9))


def _load_bundled_pretendard_gov() -> None:
    for file_name in [
        "PretendardGOV-Regular.ttf",
        "PretendardGOV-Medium.ttf",
        "PretendardGOV-SemiBold.ttf",
        "PretendardGOV-Bold.ttf",
    ]:
        font_resource = resources.files("korail_program.assets.fonts").joinpath(file_name)
        with resources.as_file(font_resource) as font_path:
            QFontDatabase.addApplicationFont(str(font_path))
