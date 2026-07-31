"""Station OCR using the same GPT vision model as the frame judge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from korail_program.judge.openai_client import (
    OpenAIVisionConfig,
    encode_image_data_url,
    extract_openai_output_text,
    post_openai_responses,
    resolve_openai_api_key,
    resolve_openai_image_detail,
)
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
    """Use a GPT vision model as a zero-install station OCR backend."""

    method = "gpt-vlm-ocr"

    def __init__(self, config: OpenAIVisionConfig | None = None) -> None:
        self.config = config or OpenAIVisionConfig()

    def read_station_text(
        self,
        image_path: str | Path,
        *,
        route_hint: str | None = None,
    ) -> VlmStationOcrResult:
        payload = _build_station_ocr_payload(
            model=self.config.model,
            image_data_url=encode_image_data_url(image_path),
            route_hint=route_hint,
            image_detail=self.config.image_detail,
            reasoning_effort=self.config.reasoning_effort,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
        )
        response_text = extract_openai_output_text(
            post_openai_responses(
                base_url=self.config.base_url,
                api_key=resolve_openai_api_key(
                    api_key=self.config.api_key,
                    api_key_env=self.config.api_key_env,
                ),
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


def _build_station_ocr_payload(
    *,
    model: str,
    image_data_url: str,
    route_hint: str | None,
    image_detail: str,
    reasoning_effort: str | None,
    temperature: float | None,
    max_output_tokens: int,
) -> dict[str, object]:
    hint = f"\nRoute/station hint: {route_hint}" if route_hint else ""
    prompt = (
        "Inspect this sampled railway video frame and read any station, route, or location "
        "text that is actually visible. Return JSON only."
        f"{hint}"
    )
    payload: dict[str, object] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": STATION_OCR_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": resolve_openai_image_detail(model, image_detail),
                    },
                ],
            },
        ],
        "text": {"format": {"type": "json_object"}},
        "max_output_tokens": max_output_tokens,
    }
    if temperature is not None and not model.lower().startswith("gpt-5"):
        payload["temperature"] = temperature
    if reasoning_effort and model.lower().startswith("gpt-5"):
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


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
