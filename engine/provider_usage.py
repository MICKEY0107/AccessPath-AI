"""Token use per run, including how much of each prompt the provider served from cache.

Every planner call sends the same fixed instructions first (``SYSTEM_INSTRUCTION`` and,
for Groq, the action schema) and only then the page observation. Providers that cache
repeated prompt prefixes (Groq, OpenAI-compatible routers, Gemini's implicit caching)
can therefore reuse the instructions on every call after the first, which cuts cost and
per-minute token use on free tiers. This module records what they report back.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


def prefix_fingerprint(text: str) -> str:
    """A short id for the fixed prompt prefix, so runs can show it never changed."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


@dataclass
class TokenUsage:
    calls: int = 0
    prompt_tokens: int = 0
    cached_prompt_tokens: int = 0
    completion_tokens: int = 0

    def add_openai(self, usage: Any) -> None:
        """OpenAI-compatible ``usage`` (Groq, OpenRouter)."""
        if not isinstance(usage, dict):
            return
        self.calls += 1
        self.prompt_tokens += _int(usage.get("prompt_tokens"))
        self.completion_tokens += _int(usage.get("completion_tokens"))
        details = usage.get("prompt_tokens_details") or {}
        cached = details.get("cached_tokens") if isinstance(details, dict) else None
        self.cached_prompt_tokens += _int(
            cached if cached is not None else usage.get("cached_tokens")
        )

    def add_gemini(self, metadata: Any) -> None:
        """Gemini ``usage_metadata`` (implicit caching reports ``cached_content_token_count``)."""
        if metadata is None:
            return
        self.calls += 1
        self.prompt_tokens += _int(getattr(metadata, "prompt_token_count", 0))
        self.cached_prompt_tokens += _int(getattr(metadata, "cached_content_token_count", 0))
        self.completion_tokens += _int(getattr(metadata, "candidates_token_count", 0))

    def add_ollama(self, document: Any) -> None:
        """Ollama reports evaluated prompt tokens; its local KV cache is not itemised."""
        if not isinstance(document, dict):
            return
        self.calls += 1
        self.prompt_tokens += _int(document.get("prompt_eval_count"))
        self.completion_tokens += _int(document.get("eval_count"))

    def as_dict(self) -> dict[str, int | float | None]:
        share = (
            round(self.cached_prompt_tokens / self.prompt_tokens, 3) if self.prompt_tokens else None
        )
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "cached_prompt_tokens": self.cached_prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cached_share": share,
        }
