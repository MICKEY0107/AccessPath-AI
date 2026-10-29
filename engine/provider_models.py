"""List the models a provider offers, for the model settings page.

Only these fixed provider addresses are ever called; the Ollama address comes from
server settings. A key is sent only to its own provider and never echoed back.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MAX_MODELS = 200


class ModelListError(RuntimeError):
    """A plain-language reason the list could not be fetched."""


def _get(url: str, headers: dict[str, str], opener, timeout: float) -> Any:
    request = Request(url, headers={"User-Agent": "AccessPathAI/1.0", **headers}, method="GET")
    try:
        with opener(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in {401, 403}:
            raise ModelListError("The provider rejected the API key.") from error
        raise ModelListError(f"The provider answered HTTP {error.code}.") from error
    except (URLError, TimeoutError) as error:
        raise ModelListError("The provider could not be reached.") from error
    except json.JSONDecodeError as error:
        raise ModelListError("The provider sent a list that could not be read.") from error


def list_models(
    provider: str,
    *,
    api_key: str = "",
    ollama_base_url: str = "",
    opener: Callable[..., Any] = urlopen,
    timeout: float = 15,
) -> list[str]:
    """Return model ids, sorted, for one provider."""
    if provider == "groq":
        if not api_key:
            raise ModelListError("Enter or save a Groq API key first.")
        data = _get(
            "https://api.groq.com/openai/v1/models",
            {"Authorization": f"Bearer {api_key}"},
            opener,
            timeout,
        )
        names = [item.get("id", "") for item in data.get("data", [])]
    elif provider == "openrouter":
        data = _get("https://openrouter.ai/api/v1/models", {}, opener, timeout)
        names = [item.get("id", "") for item in data.get("data", [])]
    elif provider == "gemini":
        if not api_key:
            raise ModelListError("Enter or save a Gemini API key first.")
        data = _get(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
            {"x-goog-api-key": api_key},
            opener,
            timeout,
        )
        names = [
            item.get("name", "")
            for item in data.get("models", [])
            if "generateContent" in (item.get("supportedGenerationMethods") or [])
        ]
    elif provider == "ollama":
        if not ollama_base_url:
            raise ModelListError("Ollama is not configured on this server (OLLAMA_BASE_URL).")
        data = _get(f"{ollama_base_url.rstrip('/')}/api/tags", {}, opener, timeout)
        names = [item.get("name", "") for item in data.get("models", [])]
    else:
        raise ModelListError(f"Model lists are not available for {quote(provider)}.")
    return sorted({name for name in names if isinstance(name, str) and name})[:MAX_MODELS]
