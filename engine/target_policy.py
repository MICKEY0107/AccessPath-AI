"""Deterministic request and browser-event policy for approved targets."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .contracts import TargetPolicyV1


@dataclass(frozen=True)
class TargetPolicyDecision:
    allowed: bool
    code: str
    fatal: bool = False


class TargetPolicy:
    """Evaluate requests against a validated, versioned target manifest."""

    def __init__(self, config: TargetPolicyV1) -> None:
        self.config = config
        self._navigation_origins = set(config.navigation_origins)
        self._resource_origins = set(config.resource_origins)
        self._allowed_methods = set(config.allowed_methods)

    def validate_start_url(self, url: str) -> None:
        decision = self.decide_request(url, method="GET", is_navigation=True)
        if not decision.allowed:
            raise ValueError(f"START_URL_NOT_ALLOWED:{decision.code}")

    def decide_request(
        self,
        url: str,
        *,
        method: str,
        is_navigation: bool,
    ) -> TargetPolicyDecision:
        if method.upper() not in self._allowed_methods:
            return TargetPolicyDecision(
                False,
                "REQUEST_METHOD_NOT_ALLOWED",
                fatal=is_navigation,
            )

        parsed = urlparse(url)
        if not is_navigation and parsed.scheme in {"about", "blob", "data"}:
            return TargetPolicyDecision(True, "REQUEST_ALLOWED")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if is_navigation:
            if origin not in self._navigation_origins:
                return TargetPolicyDecision(False, "NAVIGATION_ORIGIN_NOT_ALLOWED", fatal=True)
            path = parsed.path or "/"
            if not any(
                path.startswith(prefix)
                for prefix in self.config.navigation_path_prefixes
            ):
                return TargetPolicyDecision(False, "NAVIGATION_PATH_NOT_ALLOWED", fatal=True)
            return TargetPolicyDecision(True, "REQUEST_ALLOWED")

        if origin not in self._resource_origins:
            return TargetPolicyDecision(False, "RESOURCE_ORIGIN_NOT_ALLOWED", fatal=False)
        return TargetPolicyDecision(True, "REQUEST_ALLOWED")

    def decide_popup(self) -> TargetPolicyDecision:
        if self.config.allow_popups:
            return TargetPolicyDecision(True, "POPUP_ALLOWED")
        return TargetPolicyDecision(False, "POPUP_NOT_ALLOWED", fatal=True)

    def decide_download(self) -> TargetPolicyDecision:
        if self.config.allow_downloads:
            return TargetPolicyDecision(True, "DOWNLOAD_ALLOWED")
        return TargetPolicyDecision(False, "DOWNLOAD_NOT_ALLOWED", fatal=True)
