"""In-app PDF report preview dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from korail_program.app.widgets import ActionButton


class PdfViewerDialog(QDialog):
    """Display a saved report without leaving the application."""

    def __init__(self, pdf_path: Path, *, parent=None) -> None:
        super().__init__(parent)
        self.pdf_path = pdf_path.resolve()
        self.setObjectName("PdfViewerDialog")
        self.setWindowTitle(f"PDF 리포트 미리보기 - {self.pdf_path.name}")
        self.resize(1080, 820)
        self.setMinimumSize(780, 620)

        self.document = QPdfDocument(self)
        error = self.document.load(str(self.pdf_path))
        if error is not QPdfDocument.Error.None_:
            raise ValueError(f"PDF 파일을 불러올 수 없습니다: {error.name}")

        self.view = QPdfView()
        self.view.setObjectName("PdfViewer")
        self.view.setDocument(self.document)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        file_label = QLabel(self.pdf_path.name)
        file_label.setObjectName("CardTitle")
        file_label.setToolTip(str(self.pdf_path))

        self.page_count_label = QLabel()
        self.page_count_label.setObjectName("Muted")
        self._update_page_count(self.document.pageCount())
        self.document.pageCountChanged.connect(self._update_page_count)

        zoom_out = ActionButton(
            "",
            icon_name="magnify-minus-outline",
            compact=True,
        )
        zoom_out.setToolTip("축소")
        zoom_out.clicked.connect(lambda: self._change_zoom(0.85))
        zoom_in = ActionButton(
            "",
            icon_name="magnify-plus-outline",
            compact=True,
        )
        zoom_in.setToolTip("확대")
        zoom_in.clicked.connect(lambda: self._change_zoom(1.15))
        fit_width = ActionButton("너비 맞춤", small=True)
        fit_width.clicked.connect(
            lambda: self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        )
        close_button = ActionButton("닫기", tone="primary", small=True)
        close_button.clicked.connect(self.accept)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        toolbar.addWidget(file_label)
        toolbar.addWidget(self.page_count_label)
        toolbar.addStretch(1)
        toolbar.addWidget(zoom_out)
        toolbar.addWidget(zoom_in)
        toolbar.addWidget(fit_width)
        toolbar.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)
        layout.addLayout(toolbar)
        layout.addWidget(self.view, stretch=1)

    def _change_zoom(self, multiplier: float) -> None:
        zoom = self.view.zoomFactor()
        if zoom <= 0:
            zoom = 1.0
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(max(0.25, min(4.0, zoom * multiplier)))

    def _update_page_count(self, page_count: int) -> None:
        self.page_count_label.setText(f"{max(0, page_count)}페이지")
        self.page_count_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    def done(self, result: int) -> None:
        self.view.setDocument(None)
        self.document.close()
        super().done(result)
