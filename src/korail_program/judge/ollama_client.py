"""Local Ollama vision client used by the judge and OCR pipelines."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from korail_program.config import DEFAULT_OLLAMA_URL, DEFAULT_VISION_MODEL
from korail_program.judge.harness import build_task_payload


@dataclass(frozen=True, slots=True)
class OllamaVisionConfig:
    base_url: str = DEFAULT_OLLAMA_URL
    model: str = DEFAULT_VISION_MODEL
    timeout_s: int = 180


class OllamaApiError(RuntimeError):
    def __init__(self, *, status_code: int | None, reason: str, detail: str) -> None:
        self.status_code = status_code
        self.reason = reason
        self.detail = detail
        prefix = f"Ollama HTTP {status_code} {reason}" if status_code else f"Ollama {reason}"
        super().__init__(f"{prefix}: {detail}" if detail else prefix)


class OllamaVisionJudgeClient:
    def __init__(self, config: OllamaVisionConfig | None = None) -> None:
        self.config = config or OllamaVisionConfig()

    def judge_image(self, image_path: str | Path, *, route_hint: str | None = None) -> str:
        payload = build_task_payload(
            model=self.config.model,
            task="judge",
            image_b64=encode_image_base64(image_path),
            route_hint=route_hint,
        )
        return extract_ollama_message_content(
            post_ollama_chat(
                base_url=self.config.base_url,
                payload=payload,
                timeout_s=self.config.timeout_s,
            )
        )


def build_ollama_chat_payload(
    *, model: str, prompt: str, image_b64: str, options: dict[str, object] | None = None
) -> dict[str, object]:
    """Compatibility helper for tests and integrations that provide a custom user prompt."""

    payload = build_task_payload(model=model, task="judge", image_b64=image_b64)
    messages = payload["messages"]
    assert isinstance(messages, list)
    user_message = messages[-1]
    assert isinstance(user_message, dict)
    user_message["content"] = prompt
    if options is not None:
        payload["options"] = options
    return payload


def build_ollama_ocr_payload(
    *, model: str, image_b64: str, route_hint: str | None = None
) -> dict[str, object]:
    return build_task_payload(
        model=model,
        task="ocr",
        image_b64=image_b64,
        route_hint=route_hint,
    )


def post_ollama_chat(
    *, base_url: str, payload: dict[str, object], timeout_s: int
) -> dict[str, Any]:
    """Send a structured request with compatibility fallbacks for older model templates."""

    attempts = [payload]
    if isinstance(payload.get("format"), dict):
        json_payload = dict(payload)
        json_payload["format"] = "json"
        attempts.append(json_payload)
    plain_payload = dict(payload)
    plain_payload.pop("format", None)
    attempts.append(plain_payload)

    last_error: OllamaApiError | None = None
    for index, attempt in enumerate(attempts):
        try:
            return _post_ollama_chat_once(base_url=base_url, payload=attempt, timeout_s=timeout_s)
        except OllamaApiError as exc:
            last_error = exc
            if index == len(attempts) - 1 or exc.status_code not in {400, 500}:
                raise
    assert last_error is not None
    raise last_error


def extract_ollama_message_content(body: dict[str, Any]) -> str:
    message = body.get("message", {})
    if isinstance(message, dict) and "content" in message:
        return str(message["content"])
    if "response" in body:
        return str(body["response"])
    raise ValueError(f"Unexpected Ollama response shape: {body!r}")


def test_ollama_connection(
    *, base_url: str = DEFAULT_OLLAMA_URL, model: str | None = None, timeout_s: int = 5
) -> dict[str, Any]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise OllamaApiError(
            status_code=exc.code,
            reason=str(exc.reason),
            detail=_extract_error_detail(_read_http_error_body(exc)),
        ) from exc
    except urllib.error.URLError as exc:
        raise OllamaApiError(
            status_code=None, reason="connection error", detail=str(exc.reason)
        ) from exc
    if not isinstance(body, dict):
        raise ValueError(f"Unexpected Ollama response body: {body!r}")
    if model:
        installed = {
            str(item.get("name") or item.get("model") or "").removesuffix(":latest")
            for item in body.get("models", [])
            if isinstance(item, dict)
        }
        if model.removesuffix(":latest") not in installed:
            raise OllamaApiError(
                status_code=404,
                reason="model not installed",
                detail=f"{model} 모델을 앱에서 먼저 설치하세요.",
            )
    return body


def encode_image_base64(image_path: str | Path) -> str:
    return base64.b64encode(Path(image_path).read_bytes()).decode("ascii")


def _post_ollama_chat_once(
    *, base_url: str, payload: dict[str, object], timeout_s: int
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
        raise OllamaApiError(
            status_code=exc.code,
            reason=str(exc.reason),
            detail=_extract_error_detail(_read_http_error_body(exc)),
        ) from exc
    except urllib.error.URLError as exc:
        raise OllamaApiError(
            status_code=None, reason="connection error", detail=str(exc.reason)
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
