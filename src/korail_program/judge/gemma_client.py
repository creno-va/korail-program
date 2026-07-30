"""Local vision judge client adapters."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from korail_program.config import (
    DEFAULT_OLLAMA_NUM_CTX,
    DEFAULT_OLLAMA_TEMPERATURE,
    DEFAULT_OLLAMA_URL,
    DEFAULT_VISION_MODEL,
)
from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


@dataclass(frozen=True, slots=True)
class OllamaVisionConfig:
    base_url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_VISION_MODEL
    timeout_s: int = 120
    num_ctx: int = DEFAULT_OLLAMA_NUM_CTX
    temperature: float = DEFAULT_OLLAMA_TEMPERATURE


class OllamaApiError(RuntimeError):
    """Raised when the local Ollama API rejects a request."""

    def __init__(
        self,
        *,
        status_code: int | None,
        reason: str,
        detail: str,
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self.detail = detail
        prefix = f"Ollama HTTP {status_code} {reason}" if status_code else f"Ollama {reason}"
        super().__init__(f"{prefix}: {detail}" if detail else prefix)


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
            options=ollama_options(self.config),
        )
        return extract_ollama_message_content(
            post_ollama_chat(
                base_url=self.config.base_url,
                payload=payload,
                timeout_s=self.config.timeout_s,
            )
        )


def post_ollama_chat(
    *,
    base_url: str,
    payload: dict[str, object],
    timeout_s: int,
) -> dict[str, Any]:
    """Post to Ollama chat API and preserve actionable server errors.

    Some Ollama/model combinations can fail on structured output with images. The prompt still
    asks for JSON, so retry once without the `format` option before surfacing a 5xx error.
    """

    try:
        return _post_ollama_chat_once(base_url=base_url, payload=payload, timeout_s=timeout_s)
    except OllamaApiError as exc:
        if exc.status_code and exc.status_code >= 500 and payload.get("format") == "json":
            retry_payload = dict(payload)
            retry_payload.pop("format", None)
            return _post_ollama_chat_once(
                base_url=base_url,
                payload=retry_payload,
                timeout_s=timeout_s,
            )
        raise


def extract_ollama_message_content(body: dict[str, Any]) -> str:
    message = body.get("message", {})
    if isinstance(message, dict) and "content" in message:
        return str(message["content"])
    if "response" in body:
        return str(body["response"])
    raise ValueError(f"Unexpected Ollama response shape: {body!r}")


def _post_ollama_chat_once(
    *,
    base_url: str,
    payload: dict[str, object],
    timeout_s: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _extract_error_detail(_read_http_error_body(exc))
        raise OllamaApiError(
            status_code=exc.code,
            reason=str(exc.reason),
            detail=detail,
        ) from exc
    except urllib.error.URLError as exc:
        raise OllamaApiError(
            status_code=None,
            reason="connection error",
            detail=str(exc.reason),
        ) from exc

    if not isinstance(body, dict):
        raise ValueError(f"Unexpected Ollama response body: {body!r}")
    return body


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        return ""


def _extract_error_detail(body_text: str) -> str:
    if not body_text:
        return ""
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError:
        return body_text
    if isinstance(body, dict):
        for key in ("error", "message", "detail"):
            if key in body:
                return str(body[key])
    return body_text


def build_ollama_chat_payload(
    *,
    model: str,
    prompt: str,
    image_b64: str,
    options: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt, "images": [image_b64]},
        ],
    }
    if options:
        payload["options"] = options
    return payload


def ollama_options(config: OllamaVisionConfig) -> dict[str, object]:
    return {
        "num_ctx": config.num_ctx,
        "temperature": config.temperature,
    }


def encode_image_base64(image_path: str | Path) -> str:
    return base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
