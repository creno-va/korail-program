"""PySide6 GUI entry point."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication

        from korail_program.app.main_window import MainWindow
    except ImportError as exc:
        print("PySide6 is not installed. Install the GUI dependencies first.")
        raise SystemExit(2) from exc

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
