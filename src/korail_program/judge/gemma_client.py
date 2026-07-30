"""Local Gemma vision judge client adapters."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
import urllib.request

from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


@dataclass(frozen=True, slots=True)
class OllamaVisionConfig:
    base_url: str = "http://localhost:11434"
    model: str = "gemma3:4b"
    timeout_s: int = 120


class OllamaVisionJudgeClient:
    """Call a local Ollama-compatible vision model server."""

    def __init__(self, config: OllamaVisionConfig | None = None) -> None:
        self.config = config or OllamaVisionConfig()

    def judge_image(self, image_path: str | Path, *, route_hint: str | None = None) -> str:
        image_b64 = encode_image_base64(image_path)
        payload = build_ollama_chat_payload(
            model=self.config.model,
            prompt=build_frame_judge_prompt(route_hint=route_hint),
            image_b64=image_b64,
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
            return str(message["content"])
        if "response" in body:
            return str(body["response"])
        raise ValueError(f"Unexpected Ollama response shape: {body!r}")


def build_ollama_chat_payload(*, model: str, prompt: str, image_b64: str) -> dict[str, object]:
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt, "images": [image_b64]},
        ],
    }


def encode_image_base64(image_path: str | Path) -> str:
    return base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
