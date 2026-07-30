"""Station OCR using the same local vision model as the frame judge."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import urllib.request

from korail_program.judge.gemma_client import OllamaVisionConfig, encode_image_base64
from korail_program.judge.schema import parse_judge_json

STATION_OCR_SYSTEM_PROMPT = """
You are a focused OCR worker for Korean railway cab-video frames.
Read only visible station, route, or location text from the image.
Do not assess vegetation, catenary risk, scenery, weather, or safety conditions.
Return strict JSON with this schema:
{
  "raw_text": "all legible railway/location text, or an empty string",
  "station_name": "best station name if visible, otherwise null",
  "confidence": 0.0
}
Use Korean station names when text is Korean. If the frame has no readable station/location
text, return raw_text as "" and station_name as null.
""".strip()


@dataclass(frozen=True, slots=True)
class VlmStationOcrResult:
    raw_text: str
    station_name: str | None
    confidence: float


class VlmStationOcrEngine:
    """Use a local multimodal LLM as a zero-install station OCR backend."""

    method = "vlm-ocr"

    def __init__(self, config: OllamaVisionConfig | None = None) -> None:
        self.config = config or OllamaVisionConfig()

    def read_station_text(
        self,
        image_path: str | Path,
        *,
        route_hint: str | None = None,
    ) -> VlmStationOcrResult:
        payload = _build_station_ocr_payload(
            model=self.config.model,
            image_b64=encode_image_base64(image_path),
            route_hint=route_hint,
        )
        request = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))

        message = body.get("message", {})
        if isinstance(message, dict) and "content" in message:
            response_text = str(message["content"])
        elif "response" in body:
            response_text = str(body["response"])
        else:
            raise ValueError(f"Unexpected Ollama response shape: {body!r}")

        parsed = parse_judge_json(response_text)
        return VlmStationOcrResult(
            raw_text=_coerce_text(parsed.get("raw_text") or parsed.get("text")),
            station_name=_coerce_optional_text(parsed.get("station_name")),
            confidence=_coerce_probability(parsed.get("confidence")),
        )


def _build_station_ocr_payload(
    *,
    model: str,
    image_b64: str,
    route_hint: str | None,
) -> dict[str, object]:
    hint = f"\nRoute/station hint: {route_hint}" if route_hint else ""
    prompt = (
        "Inspect this sampled railway video frame and read any station, route, or location "
        "text that is actually visible. Return JSON only."
        f"{hint}"
    )
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": STATION_OCR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt, "images": [image_b64]},
        ],
    }


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_optional_text(value: Any) -> str | None:
    text = _coerce_text(value)
    if not text or text.lower() in {"none", "null", "unknown", "n/a", "-"}:
        return None
    return text


def _coerce_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))
