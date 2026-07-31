"""OpenAI vision judge client adapters."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from korail_program.config import (
    DEFAULT_OPENAI_API_KEY_ENV,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_IMAGE_DETAIL,
    DEFAULT_OPENAI_REASONING_EFFORT,
    DEFAULT_VISION_MODEL,
)
from korail_program.judge.prompts import JUDGE_SYSTEM_PROMPT, build_frame_judge_prompt


@dataclass(frozen=True, slots=True)
class OpenAIVisionConfig:
    base_url: str = DEFAULT_OPENAI_BASE_URL
    model: str = DEFAULT_VISION_MODEL
    timeout_s: int = 120
    api_key: str | None = None
    api_key_env: str = DEFAULT_OPENAI_API_KEY_ENV
    image_detail: str = DEFAULT_OPENAI_IMAGE_DETAIL
    reasoning_effort: str | None = DEFAULT_OPENAI_REASONING_EFFORT
    temperature: float | None = None
    max_output_tokens: int = 900


class OpenAIApiError(RuntimeError):
    """Raised when the OpenAI API rejects a request."""

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
        prefix = f"OpenAI HTTP {status_code} {reason}" if status_code else f"OpenAI {reason}"
        super().__init__(f"{prefix}: {detail}" if detail else prefix)


class MissingOpenAIApiKeyError(OpenAIApiError):
    """Raised when no OpenAI API key is configured."""

    def __init__(self, api_key_env: str = DEFAULT_OPENAI_API_KEY_ENV) -> None:
        super().__init__(
            status_code=None,
            reason="API key missing",
            detail=f"Set {api_key_env} or save an API key in the app settings.",
        )


class OpenAIVisionJudgeClient:
    """Call OpenAI's vision-capable Responses API for frame judging."""

    def __init__(self, config: OpenAIVisionConfig | None = None) -> None:
        self.config = config or OpenAIVisionConfig()

    def judge_image(self, image_path: str | Path, *, route_hint: str | None = None) -> str:
        payload = build_openai_responses_payload(
            model=self.config.model,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            prompt=build_frame_judge_prompt(route_hint=route_hint),
            image_data_url=encode_image_data_url(image_path),
            image_detail=self.config.image_detail,
            reasoning_effort=self.config.reasoning_effort,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
        )
        return extract_openai_output_text(
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


def resolve_openai_api_key(
    *,
    api_key: str | None = None,
    api_key_env: str = DEFAULT_OPENAI_API_KEY_ENV,
) -> str:
    value = (api_key or os.environ.get(api_key_env) or "").strip()
    if not value:
        raise MissingOpenAIApiKeyError(api_key_env)
    return value


def post_openai_responses(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, object],
    timeout_s: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    body = _open_openai_json(request, timeout_s=timeout_s)

    if not isinstance(body, dict):
        raise ValueError(f"Unexpected OpenAI response body: {body!r}")
    return body


def test_openai_connection(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_s: int = 20,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/models/{quote(model, safe='')}",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    body = _open_openai_json(request, timeout_s=timeout_s)
    if not isinstance(body, dict):
        raise ValueError(f"Unexpected OpenAI response body: {body!r}")
    return body


def extract_openai_output_text(body: dict[str, Any]) -> str:
    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    texts: list[str] = []
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                texts.append(text)
    if texts:
        return "\n".join(texts)
    raise ValueError(f"Unexpected OpenAI response shape: {body!r}")


def build_openai_responses_payload(
    *,
    model: str,
    system_prompt: str,
    prompt: str,
    image_data_url: str,
    image_detail: str,
    reasoning_effort: str | None,
    temperature: float | None,
    max_output_tokens: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
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
    if temperature is not None and not _is_gpt5_family(model):
        payload["temperature"] = temperature
    if reasoning_effort and _supports_reasoning(model):
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


def _supports_reasoning(model: str) -> bool:
    return _is_gpt5_family(model)


def _is_gpt5_family(model: str) -> bool:
    return model.lower().startswith("gpt-5")


def encode_image_data_url(image_path: str | Path) -> str:
    path = Path(image_path)
    mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime_type};base64,{encode_image_base64(path)}"


def resolve_openai_image_detail(model: str, detail: str) -> str:
    normalized = model.lower()
    if detail == "original" and not normalized.startswith(("gpt-5.6", "gpt-5.5", "gpt-5.4")):
        return "high"
    return detail


def encode_image_base64(image_path: str | Path) -> str:
    return base64.b64encode(Path(image_path).read_bytes()).decode("ascii")


def _open_openai_json(request: urllib.request.Request, *, timeout_s: int) -> dict[str, Any]:
    try:
        with _urlopen_with_certifi_fallback(request, timeout_s=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _extract_error_detail(_read_http_error_body(exc))
        raise OpenAIApiError(
            status_code=exc.code,
            reason=str(exc.reason),
            detail=detail,
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenAIApiError(
            status_code=None,
            reason=_connection_error_reason(exc),
            detail=_connection_error_detail(exc),
        ) from exc


def _urlopen_with_certifi_fallback(
    request: urllib.request.Request,
    *,
    timeout_s: int,
):
    try:
        return urllib.request.urlopen(request, timeout=timeout_s)
    except urllib.error.URLError as exc:
        if not _is_certificate_error(exc):
            raise
        context = _certifi_ssl_context()
        if context is None:
            raise
        try:
            return urllib.request.urlopen(request, timeout=timeout_s, context=context)
        except urllib.error.URLError as fallback_exc:
            if _is_certificate_error(fallback_exc):
                raise _merge_certificate_errors(exc, fallback_exc) from fallback_exc
            raise


def _certifi_ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _is_certificate_error(exc: urllib.error.URLError) -> bool:
    reason = exc.reason
    if isinstance(reason, ssl.SSLCertVerificationError):
        return True
    if isinstance(reason, ssl.SSLError):
        return "certificate" in str(reason).lower()
    return "certificate" in str(reason).lower()


def _merge_certificate_errors(
    original: urllib.error.URLError,
    fallback: urllib.error.URLError,
) -> urllib.error.URLError:
    return urllib.error.URLError(
        "SSL certificate verification failed. "
        f"OS trust store error: {original.reason}; bundled CA error: {fallback.reason}"
    )


def _connection_error_reason(exc: urllib.error.URLError) -> str:
    if _is_certificate_error(exc):
        return "SSL certificate verification failed"
    return "connection error"


def _connection_error_detail(exc: urllib.error.URLError) -> str:
    if _is_certificate_error(exc):
        return (
            f"{exc.reason}. PC time, antivirus HTTPS scanning, company proxy, "
            "or missing root CA can cause this. If your network uses a custom CA, "
            "set SSL_CERT_FILE to that CA bundle path."
        )
    return str(exc.reason)


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
        error = body.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "code", "type"):
                if error.get(key):
                    return str(error[key])
        for key in ("message", "detail", "error"):
            if body.get(key):
                return str(body[key])
    return body_text
