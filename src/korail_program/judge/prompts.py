"""Prompt templates for frame-level VQA judging."""

from __future__ import annotations

JUDGE_SYSTEM_PROMPT = """
You are an offline railway inspection assistant.
Judge only what is visible in the image. Avoid flagging ordinary trackside vegetation
unless it is visually close to the overhead catenary clearance area.
Return JSON only. Do not include markdown or explanation outside the JSON object.
""".strip()


def build_frame_judge_prompt(*, route_hint: str | None = None) -> str:
    route_line = f"Route hint: {route_hint}\n" if route_hint else ""
    return (
        f"{route_line}"
        "Task: Inspect this forward-facing train cab frame.\n"
        "Decide whether trees, bamboo, grass, branches, or other vegetation appear close to "
        "the catenary, overhead wire, messenger wire, or pantograph clearance area.\n"
        "Do not mark vegetation as risky only because it is visible beside the track, below "
        "the rail line, on embankments, or far from the overhead wires. Risk requires a clear "
        "spatial relationship with the overhead line corridor.\n"
        "Return this JSON schema exactly:\n"
        "{\n"
        '  "has_tree": true | false,\n'
        '  "bamboo_likely": 0.0,\n'
        '  "near_catenary": true | false,\n'
        '  "risk_level": "높음" | "중간" | "낮음" | "없음",\n'
        '  "bbox_hint": [x1, y1, x2, y2] | null,\n'
        '  "evidence": "one Korean sentence",\n'
        '  "needs_human_review": true | false\n'
        "}\n"
        "Risk guide:\n"
        "- 높음: vegetation visibly overlaps, touches, crosses, or nearly touches the overhead line.\n"
        "- 중간: vegetation reaches into the overhead clearance corridor and needs review.\n"
        "- 낮음: vegetation is visible but not clearly near the overhead line.\n"
        "- 없음: no obstruction vegetation is visible.\n"
        "Set near_catenary=false when wires and vegetation are separated by clear empty space.\n"
        "Set bbox_hint around the vegetation near the line, not around all roadside greenery.\n"
        "If the perspective is ambiguous, set needs_human_review=true.\n"
    )
