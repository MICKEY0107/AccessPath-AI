"""Which AI providers may read a private repository's code.

Reviewed 29 October 2026 against the providers' published terms:

* Gemini API free tier: Google uses prompts and responses to improve its products,
  human reviewers may read them, and the terms say not to submit confidential
  information (https://ai.google.dev/terms).
* Groq: does not retain request data by default, keeps abuse-monitoring logs up to
  30 days, and offers Zero Data Retention (https://console.groq.com/docs/your-data).
* OpenRouter: routes each call to another provider with its own data policy; the
  ``openrouter/free`` router picks a random free model.
* Ollama: runs on your own machine, so code never leaves it.

A provider can be allowed explicitly with the CODE_SAFE_PROVIDERS setting (for
example when a team uses a paid tier with a data agreement).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodeSafety:
    safe: bool
    label: str
    reason: str


def code_safety(provider: str, model: str = "", allowed: tuple[str, ...] = ()) -> CodeSafety:
    if provider in allowed:
        return CodeSafety(True, "Allowed by server setting", "Marked safe in CODE_SAFE_PROVIDERS.")
    if provider == "ollama":
        return CodeSafety(True, "OK for private code", "Runs on your machine; code never leaves it.")
    if provider == "groq":
        return CodeSafety(
            True,
            "OK for private code",
            "Groq keeps no request data by default (abuse logs up to 30 days); turn on Zero "
            "Data Retention in Groq's Data Controls for none at all.",
        )
    if provider == "gemini":
        return CodeSafety(
            False,
            "Not for private code",
            "Gemini's free-tier terms let Google use prompts to improve its products and let "
            "people review them, and say not to send confidential information.",
        )
    if provider == "openrouter":
        if model == "openrouter/free" or model.endswith(":free"):
            reason = "openrouter/free sends each call to a random free provider with its own terms."
        else:
            reason = "OpenRouter passes code to another provider whose data policy varies."
        return CodeSafety(False, "Not for private code", reason)
    return CodeSafety(False, "No AI", "This planner does not send code anywhere.")
