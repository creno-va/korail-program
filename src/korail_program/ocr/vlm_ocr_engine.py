"""Station OCR using the selected local Ollama vision model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from korail_program.judge.ollama_client import (
    OllamaVisionConfig,
    build_ollama_ocr_payload,
    encode_image_base64,
    extract_ollama_message_content,
    post_ollama_chat,
)
from korail_program.judge.schema import parse_judge_json


@dataclass(frozen=True, slots=True)
class VlmStationOcrResult:
    raw_text: str
    station_name: str | None
    confidence: float


class VlmStationOcrEngine:
    method = "ollama-vlm-ocr"

    def __init__(self, config: OllamaVisionConfig | None = None) -> None:
        self.config = config or OllamaVisionConfig()

    def read_station_text(
        self, image_path: str | Path, *, route_hint: str | None = None
    ) -> VlmStationOcrResult:
        payload = build_ollama_ocr_payload(
            model=self.config.model,
            image_b64=encode_image_base64(image_path),
            route_hint=route_hint,
        )
        response_text = extract_ollama_message_content(
            post_ollama_chat(
                base_url=self.config.base_url,
                payload=payload,
                timeout_s=self.config.timeout_s,
            )
        )
        parsed = parse_judge_json(response_text)
        return VlmStationOcrResult(
            raw_text=_coerce_text(parsed.get("raw_text") or parsed.get("text")),
            station_name=_coerce_optional_text(parsed.get("station_name")),
            confidence=_coerce_probability(parsed.get("confidence")),
        )


def _coerce_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _coerce_optional_text(value: Any) -> str | None:
    text = _coerce_text(value)
    return None if not text or text.lower() in {"none", "null", "unknown", "n/a", "-"} else text


def _coerce_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
