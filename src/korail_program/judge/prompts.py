"""Prompt templates for frame-level VQA judging."""

from __future__ import annotations

JUDGE_SYSTEM_PROMPT = """
You are an offline railway inspection assistant.
Judge only what is visible in the image. Do not use green color, background hills,
distant forest, or mountains as evidence of an obstruction.
Flag vegetation only when a foreground or midground tree, bamboo, branch, or canopy
physically intrudes into the overhead catenary clearance area.
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
        "Do not raise risk for green pixels alone. Do not mark background mountains, hills, "
        "distant forest, continuous skyline vegetation, roadside grass, embankment plants, "
        "or scenery behind the wires as risky merely because perspective places them near "
        "the overhead line in the image.\n"
        "Risk requires a local obstructing plant connected to the trackside foreground or "
        "midground and a clear physical relationship with the overhead line corridor. If you "
        "cannot point to the offending branch/canopy with a tight bbox, downgrade the risk.\n"
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
        "- 높음: foreground/midground vegetation overlaps, touches, crosses, or nearly "
        "touches the overhead line.\n"
        "- 중간: a nearby branch/canopy enters the overhead clearance corridor, but "
        "contact is uncertain.\n"
        "- 낮음: nearby vegetation exists along the route but stays below/aside from "
        "the overhead corridor.\n"
        "- 없음: no foreground or midground obstruction vegetation is visible.\n"
        "Set risk_level to 없음 or 낮음 when the only vegetation is a background mountain, "
        "far hillside, distant forest, or green scenery separated from the track corridor.\n"
        "Set near_catenary=false when vegetation is behind the wires, below the line, part of "
        "a distant landscape, or separated by clear empty space.\n"
        "Set bbox_hint tightly around only the suspected obstructing branch/canopy. Do not "
        "box all roadside greenery or a distant mountain/forest background.\n"
        "If perspective alone makes background greenery look close to a wire, downgrade and "
        "set needs_human_review=true rather than increasing the risk.\n"
    )
