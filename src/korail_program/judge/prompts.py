"""Prompt templates for frame-level VQA judging."""

from __future__ import annotations

JUDGE_SYSTEM_PROMPT = """
You are an offline railway inspection assistant.
Judge only what is visible in the image. Do not use green color, background hills,
distant forest, or mountains as evidence of an obstruction.
Frames are sampled sparsely, so inspect the full visible track corridor ahead, including
specific trees that appear small or farther from the camera. Camera distance alone is never
a reason to downgrade a specific trackside tree, bamboo, branch, or canopy that is aligned
with, intrudes into, or visibly narrows the overhead catenary clearance corridor.
Prefer recall at the 중간/낮음 boundary: choose 중간 when a specific plant ahead appears to
enter the corridor or when a safe clearance gap cannot be confirmed because of distance,
perspective, or occlusion. Use 낮음 only when a visible empty gap keeps it outside the
clearance corridor, and use 낮음 as a watchlist instead of 없음 for uncertain trackside plants.
Return JSON only. Do not include markdown or explanation outside the JSON object.
""".strip()


def build_frame_judge_prompt(*, route_hint: str | None = None) -> str:
    route_line = f"Route hint: {route_hint}\n" if route_hint else ""
    return (
        f"{route_line}"
        "Task: Inspect this forward-facing train cab frame.\n"
        "Decide whether a specific foreground or midground tree, bamboo stem, branch, or "
        "canopy intrudes into the catenary, overhead wire, messenger wire, feeder line, "
        "support bracket, or pantograph clearance area.\n"
        "The video is inspected through sparse samples rather than continuously. Evaluate "
        "the entire visible track alignment ahead: a specific plant farther down the same "
        "track may be reached before another sampled frame and must not be treated as safe "
        "merely because it looks small or distant from the camera.\n"
        "Do not raise risk for green pixels alone. Do not mark background mountains, hills, "
        "distant forest, continuous skyline vegetation, roadside grass, embankment plants, "
        "or scenery behind the wires as risky merely because perspective places them near "
        "the overhead line in the image.\n"
        "Distinguish background scenery from a specific local plant rooted beside the same "
        "track alignment. Risk requires a local obstructing plant and a physical relationship "
        "with the overhead corridor, but the plant may be in the farther midground. If a "
        "specific offending branch/canopy can be localized, use a tight bbox even when the "
        "target occupies few pixels. Do not downgrade only because the bbox is small.\n"
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
        "- 높음: a specific plant overlaps, touches, crosses, or leaves an extremely narrow "
        "gap to the overhead line or clearance corridor, regardless of camera distance.\n"
        "- 중간: a specific branch/canopy ahead enters or visibly narrows the projected "
        "overhead clearance corridor, but contact cannot be confirmed. Also use 중간 when "
        "distance, perspective, blur, or partial occlusion prevents confirming a safe gap.\n"
        "- 낮음: a specific trackside plant merits monitoring, but a visible empty gap "
        "clearly keeps it outside the overhead clearance corridor in this frame.\n"
        "- 없음: no specific obstruction vegetation associated with the track corridor "
        "is visible.\n"
        "At the 중간/낮음 boundary, choose 중간 when the plant aligns with the train's path "
        "and you cannot positively verify clear separation from the wire corridor. Do not "
        "require contact or a large foreground appearance for 중간.\n"
        "Set risk_level to 없음 or 낮음 when the only vegetation is a background mountain, "
        "far hillside, distant forest, or green scenery separated from the track corridor.\n"
        "Use 낮음, not 없음, when a specific nearby branch, bamboo stem, or canopy is visible "
        "near either side of the track and its distance from the wire corridor is uncertain.\n"
        "Set near_catenary=true for 중간 or 높음. Set it false only when vegetation is part "
        "of distant scenery or a visible empty gap clearly separates it from the corridor.\n"
        "Set bbox_hint tightly around only the suspected obstructing branch/canopy. Do not "
        "box all roadside greenery or a distant mountain/forest background.\n"
        "If perspective alone makes non-local background greenery look close to a wire, "
        "downgrade it. If perspective or distance instead limits confidence for a specific "
        "plant on the track alignment, keep 중간 and set needs_human_review=true.\n"
    )
