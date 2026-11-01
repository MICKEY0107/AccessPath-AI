"""Saved sign-ins for journeys behind a login, as Playwright storage state.

A person signs in once in their own browser window (``python -m accesspath login``),
and the resulting storage state (cookies and local storage) is reused for runs. It is
never typed by the AI, never shown back, and before use it is cut down to the journey's
own sites, so a session for one site can never leak to another.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

MAX_BYTES = 1_000_000
MAX_COOKIES = 300


class SessionStateError(ValueError):
    """A plain-language reason the saved session cannot be used."""


def _host_matches(cookie_domain: str, host: str) -> bool:
    domain = cookie_domain.lstrip(".").lower()
    host = host.lower()
    return host == domain or host.endswith("." + domain)


def parse_storage_state(raw: str | bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise SessionStateError("The saved session is larger than 1 MB.")
    try:
        state = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise SessionStateError("The saved session is not valid JSON.") from error
    if not isinstance(state, dict) or not isinstance(state.get("cookies", []), list):
        raise SessionStateError("This is not a Playwright storage state file.")
    if not isinstance(state.get("origins", []), list):
        raise SessionStateError("This is not a Playwright storage state file.")
    return state


def limit_to_origins(state: dict[str, Any], origins: list[str]) -> dict[str, Any]:
    """Keep only cookies and storage for the journey's own sites."""
    hosts = {(urlparse(origin).hostname or "").lower() for origin in origins}
    allowed = {origin.rstrip("/").lower() for origin in origins}
    cookies = [
        cookie
        for cookie in state.get("cookies", [])[:MAX_COOKIES]
        if isinstance(cookie, dict)
        and any(_host_matches(str(cookie.get("domain", "")), host) for host in hosts if host)
    ]
    storage = [
        entry
        for entry in state.get("origins", [])
        if isinstance(entry, dict) and str(entry.get("origin", "")).rstrip("/").lower() in allowed
    ]
    return {"cookies": cookies, "origins": storage}


def describe(state: dict[str, Any]) -> str:
    sites = sorted(
        {str(cookie.get("domain", "")).lstrip(".") for cookie in state.get("cookies", [])}
    )
    return f"{len(state.get('cookies', []))} cookies for {', '.join(sites) or 'no site'}"
