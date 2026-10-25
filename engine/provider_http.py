"""Shared, credential-safe helpers for OpenAI-compatible provider HTTP errors."""

from __future__ import annotations

import json
import re
from urllib.error import HTTPError

MAX_PROVIDER_MESSAGE_LENGTH = 240


def redact(text: str, api_key: str) -> str:
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return re.sub(r"(?i)(key|api_key|token)=([^&\s]+)", r"\1=[redacted]", text)


def provider_error_message(error: HTTPError, api_key: str) -> str:
    """Return ': <provider message>' from an error body, or '' when there is none."""
    try:
        body = error.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    message = ""
    try:
        document = json.loads(body)
    except json.JSONDecodeError:
        document = None
    if isinstance(document, dict):
        candidate = document.get("error")
        if isinstance(candidate, dict):
            message = str(candidate.get("message") or "")
        elif isinstance(candidate, str):
            message = candidate
    if not message:
        return ""
    message = " ".join(redact(message, api_key).split())
    return f": {message[:MAX_PROVIDER_MESSAGE_LENGTH]}"


def retry_after_seconds(error: HTTPError, message: str = "") -> float | None:
    """Read a numeric Retry-After header, else a "try again in 9.3s" hint in the message."""
    headers = getattr(error, "headers", None)
    value = headers.get("Retry-After") if headers is not None else None
    if value is None:
        hint = re.search(r"try again in ([0-9]+(?:\.[0-9]+)?)s", message)
        value = hint.group(1) if hint else None
    try:
        seconds = float(value) if value is not None else None
    except ValueError:
        return None
    return seconds if seconds is not None and seconds >= 0 else None


def completion_hint(document: object) -> str:
    """Explain a contentless completion in plain words when the cause is known."""
    if not isinstance(document, dict):
        return ""
    choices = document.get("choices")
    if (
        isinstance(choices, list)
        and choices
        and isinstance(choices[0], dict)
        and choices[0].get("finish_reason") == "length"
    ):
        return " (the model ran out of output tokens before writing its answer)"
    return ""
