"""Validation helpers for multimodal judge responses."""

from __future__ import annotations

import json
import re
from typing import Any

from korail_program.core.models import JudgeObservation, RiskLevel

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(?P<body>.*?)\s*```", re.DOTALL | re.IGNORECASE)


def parse_judge_json(text: str) -> dict[str, Any]:
    """Parse the JSON object returned by a VLM judge.

    The prompt asks for JSON only, but local models can still wrap responses in code fences.
    This function accepts that small amount of noise while rejecting non-object payloads.
    """

    cleaned = text.strip()
    fenced = _FENCED_JSON_RE.search(cleaned)
    if fenced:
        cleaned = fenced.group("body").strip()
    elif not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]

    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Judge response must be a JSON object")
    return payload


def judge_observation_from_payload(
    *,
    video_id: int,
    video_time_ms: int,
    payload: dict[str, Any],
) -> JudgeObservation:
    risk_level = RiskLevel.coerce(payload.get("risk_level"))
    bamboo_likely = _coerce_probability(payload.get("bamboo_likely", 0.0))
    has_tree = _coerce_bool(payload.get("has_tree", risk_level is not RiskLevel.NONE))
    near_catenary = _coerce_bool(payload.get("near_catenary", risk_level.priority >= 2))
    needs_human_review = _coerce_bool(
        payload.get("needs_human_review", bamboo_likely < 0.6 or risk_level is RiskLevel.NONE)
    )

    return JudgeObservation(
        video_id=video_id,
        video_time_ms=video_time_ms,
        has_tree=has_tree,
        bamboo_likely=bamboo_likely,
        near_catenary=near_catenary,
        risk_level=risk_level,
        bbox_hint=_coerce_bbox(payload.get("bbox_hint")),
        evidence=str(payload.get("evidence", "")).strip(),
        needs_human_review=needs_human_review,
    )


def judge_observation_from_text(
    *,
    video_id: int,
    video_time_ms: int,
    text: str,
) -> JudgeObservation:
    return judge_observation_from_payload(
        video_id=video_id,
        video_time_ms=video_time_ms,
        payload=parse_judge_json(text),
    )


def _coerce_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(1.0, number))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"true", "yes", "y", "1", "있음", "예", "위험", "주의", "중간", "높음"}


def _coerce_bbox(value: Any) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(round(float(item))) for item in value)
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)
