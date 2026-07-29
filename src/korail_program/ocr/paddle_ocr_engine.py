"""PaddleOCR adapter used by the OCR pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PaddleOcrConfig:
    lang: str = "korean"
    use_angle_cls: bool = True


class PaddleOcrEngine:
    """Thin optional wrapper around PaddleOCR.

    The import is delayed so core tests and CLI utilities can run before OCR dependencies
    are installed on the target Windows machine.
    """

    def __init__(self, config: PaddleOcrConfig | None = None) -> None:
        self.config = config or PaddleOcrConfig()
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError("PaddleOCR is not installed. Install OCR dependencies first.") from exc

        self._engine = PaddleOCR(lang=self.config.lang, use_angle_cls=self.config.use_angle_cls)

    def read_text(self, image_path: str | Path) -> tuple[str, float]:
        result = self._engine.ocr(str(image_path), cls=self.config.use_angle_cls)
        texts: list[str] = []
        confidences: list[float] = []
        for text, confidence in _iter_ocr_texts(result):
            texts.append(text)
            confidences.append(confidence)
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n".join(texts), average_confidence


def _iter_ocr_texts(result: Any) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    if not result:
        return items

    for page in result:
        if not page:
            continue
        for line in page:
            if not line or len(line) < 2:
                continue
            text_info = line[1]
            if not isinstance(text_info, list | tuple) or len(text_info) < 2:
                continue
            text = str(text_info[0])
            try:
                confidence = float(text_info[1])
            except (TypeError, ValueError):
                confidence = 0.0
            items.append((text, confidence))
    return items

