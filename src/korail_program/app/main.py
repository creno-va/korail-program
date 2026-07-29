"""PySide6 GUI entry point."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError as exc:
        print("PySide6 is not installed. Install the GUI dependencies first.")
        raise SystemExit(2) from exc

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Korail Obstruction Analyzer")
    window.resize(1200, 800)
    window.setCentralWidget(QLabel("Korail Obstruction Analyzer"))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

