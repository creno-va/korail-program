"""Per-family prompt and decoding harnesses for supported Ollama vision models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from korail_program.config import DEFAULT_OLLAMA_KEEP_ALIVE, DEFAULT_OLLAMA_NUM_CTX
from korail_program.judge.prompts import (
    JUDGE_SYSTEM_PROMPT,
    STATION_OCR_SYSTEM_PROMPT,
    build_frame_judge_prompt,
    build_station_ocr_prompt,
)

JUDGE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "has_tree": {"type": "boolean"},
        "bamboo_likely": {"type": "number", "minimum": 0, "maximum": 1},
        "near_catenary": {"type": "boolean"},
        "risk_level": {"type": "string", "enum": ["high", "medium", "low", "none"]},
        "bbox_hint": {
            "anyOf": [
                {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                },
                {"type": "null"},
            ]
        },
        "evidence": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
    },
    "required": [
        "has_tree",
        "bamboo_likely",
        "near_catenary",
        "risk_level",
        "bbox_hint",
        "evidence",
        "needs_human_review",
    ],
    "additionalProperties": False,
}

OCR_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "raw_text": {"type": "string"},
        "station_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["raw_text", "station_name", "confidence"],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class ModelHarness:
    family: str
    system_suffix: str
    judge_suffix: str
    ocr_suffix: str
    options: dict[str, object]
    think: bool = False

    def system_prompt(self, task: str) -> str:
        base = JUDGE_SYSTEM_PROMPT if task == "judge" else STATION_OCR_SYSTEM_PROMPT
        return f"{base}\n{self.system_suffix}".strip()

    def user_prompt(self, task: str, *, route_hint: str | None = None) -> str:
        if task == "judge":
            base = build_frame_judge_prompt(route_hint=route_hint)
            suffix = self.judge_suffix
        else:
            base = build_station_ocr_prompt(route_hint=route_hint)
            suffix = self.ocr_suffix
        return f"{base}\n{suffix}".strip()


_QWEN_HARNESS = ModelHarness(
    family="qwen",
    system_suffix=(
        "Use Qwen visual grounding carefully: determine track geometry before classifying risk. "
        "Keep reasoning internal and place only the final fields in JSON."
    ),
    judge_suffix=(
        "Qwen instruction: verify the suspected plant against the overhead corridor in spatial "
        "order. Use actual image pixel coordinates, not normalized 0..1000 coordinates."
    ),
    ocr_suffix=(
        "Qwen instruction: use multilingual scene-text recognition; separate a station name from "
        "surrounding signs and never translate Korean text."
    ),
    options={
        "num_ctx": DEFAULT_OLLAMA_NUM_CTX,
        "num_predict": 512,
        "temperature": 0.0,
        "top_p": 0.9,
        "top_k": 20,
        "seed": 42,
    },
)

_GEMMA4_HARNESS = ModelHarness(
    family="gemma4",
    system_suffix=(
        "Follow the system role directly. Do not emit thought tags or an analysis trace. Return "
        "the final structured answer only."
    ),
    judge_suffix=(
        "Gemma 4 instruction: first separate local trackside vegetation from landscape, then "
        "compare the local plant to the catenary corridor. Recheck any medium/high decision for "
        "perspective-only false positives."
    ),
    ocr_suffix=(
        "Gemma 4 instruction: transcribe only visible glyphs. Prefer null over completing a "
        "partially hidden station name from memory."
    ),
    options={
        "num_ctx": DEFAULT_OLLAMA_NUM_CTX,
        "num_predict": 512,
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 64,
        "seed": 42,
    },
)


def _variant(
    base: ModelHarness,
    *,
    judge_suffix: str,
    ocr_suffix: str,
    num_predict: int,
) -> ModelHarness:
    options = dict(base.options)
    options["num_predict"] = num_predict
    return ModelHarness(
        family=base.family,
        system_suffix=base.system_suffix,
        judge_suffix=f"{base.judge_suffix}\nModel-size instruction: {judge_suffix}",
        ocr_suffix=f"{base.ocr_suffix}\nModel-size instruction: {ocr_suffix}",
        options=options,
        think=base.think,
    )


_MODEL_HARNESSES: dict[str, ModelHarness] = {
    "qwen3-vl:2b": _variant(
        _QWEN_HARNESS,
        judge_suffix=(
            "Use the four numbered checks once, keep evidence very short, and do not describe "
            "irrelevant objects."
        ),
        ocr_suffix="Return only the clearest one or two railway text candidates.",
        num_predict=320,
    ),
    "qwen3-vl:4b": _variant(
        _QWEN_HARNESS,
        judge_suffix=(
            "Use the full checklist and verify that the chosen bbox belongs to the same track "
            "corridor as the overhead wire."
        ),
        ocr_suffix="Cross-check the station-name field against the complete visible raw text.",
        num_predict=448,
    ),
    "qwen3-vl:8b": _variant(
        _QWEN_HARNESS,
        judge_suffix=(
            "Perform a second visual verification of foreground/background separation and the "
            "wire-to-plant gap before finalizing medium or high."
        ),
        ocr_suffix="Check small, blurred and oblique Korean text before returning null.",
        num_predict=512,
    ),
    "gemma4:e2b": _variant(
        _GEMMA4_HARNESS,
        judge_suffix=(
            "Use a concise corridor-versus-landscape comparison and one short Korean evidence "
            "sentence."
        ),
        ocr_suffix="Transcribe only the single clearest relevant sign.",
        num_predict=320,
    ),
    "gemma4:e4b": _variant(
        _GEMMA4_HARNESS,
        judge_suffix=(
            "Apply the two-stage local-plant and clearance-gap check without adding narrative "
            "outside the fields."
        ),
        ocr_suffix="Compare all visible railway text before choosing station_name.",
        num_predict=448,
    ),
    "gemma4:12b": _variant(
        _GEMMA4_HARNESS,
        judge_suffix=(
            "Recheck corridor geometry, perspective-only false positives, and consistency among "
            "risk_level, near_catenary and bbox_hint."
        ),
        ocr_suffix="Recheck ambiguous Korean glyphs while refusing to complete hidden text.",
        num_predict=512,
    ),
}


def harness_for_model(model: str) -> ModelHarness:
    normalized = model.strip().lower().removesuffix(":latest")
    if normalized in _MODEL_HARNESSES:
        return _MODEL_HARNESSES[normalized]
    if normalized.startswith("gemma4"):
        return _GEMMA4_HARNESS
    return _QWEN_HARNESS


def build_task_payload(
    *,
    model: str,
    task: str,
    image_b64: str,
    route_hint: str | None = None,
) -> dict[str, object]:
    if task not in {"judge", "ocr"}:
        raise ValueError(f"Unsupported harness task: {task!r}")
    harness = harness_for_model(model)
    schema = JUDGE_JSON_SCHEMA if task == "judge" else OCR_JSON_SCHEMA
    return {
        "model": model,
        "stream": False,
        "format": schema,
        "think": harness.think,
        "keep_alive": DEFAULT_OLLAMA_KEEP_ALIVE,
        "messages": [
            {"role": "system", "content": harness.system_prompt(task)},
            {
                "role": "user",
                "content": harness.user_prompt(task, route_hint=route_hint),
                "images": [image_b64],
            },
        ],
        "options": dict(harness.options),
    }
