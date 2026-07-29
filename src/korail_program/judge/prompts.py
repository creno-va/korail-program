"""Prompt templates for frame-level VQA judging."""

from __future__ import annotations

JUDGE_SYSTEM_PROMPT = """
You are an offline railway inspection assistant.
Judge only what is visible in the image. Be conservative about false negatives.
Return JSON only. Do not include markdown or explanation outside the JSON object.
""".strip()


def build_frame_judge_prompt(*, route_hint: str | None = None) -> str:
    route_line = f"Route hint: {route_hint}\n" if route_hint else ""
    return (
        f"{route_line}"
        "Task: Inspect this forward-facing train cab frame.\n"
        "Decide whether trees, bamboo, or vegetation appear near the catenary/overhead line.\n"
        "Use the following JSON schema exactly:\n"
        "{\n"
        '  "has_tree": true | false,\n'
        '  "bamboo_likely": 0.0,\n'
        '  "near_catenary": true | false,\n'
        '  "risk_level": "상" | "중" | "하" | "없음",\n'
        '  "bbox_hint": [x1, y1, x2, y2] | null,\n'
        '  "evidence": "one Korean sentence",\n'
        '  "needs_human_review": true | false\n'
        "}\n"
        "Risk guide:\n"
        "- 상: vegetation overlaps or appears extremely close to catenary/overhead line.\n"
        "- 중: vegetation is close enough to require warning-level review.\n"
        "- 하: vegetation is visible but not clearly near the line.\n"
        "- 없음: no obstruction vegetation is visible.\n"
    )

