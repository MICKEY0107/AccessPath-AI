"""Journey files: one keyboard task, described in JSON (or YAML when PyYAML is installed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.contracts import ActionKind
from engine.rules import RuleConfigV1, load_catalog

SCHEMA = "accesspath_journey.v1"


class PlanStepV1(BaseModel):
    """One key press of a scripted (replayable) plan."""

    model_config = ConfigDict(extra="forbid")

    action: ActionKind
    value: str | None = Field(default=None, max_length=500)
    target_hint: str = Field(default="", max_length=200)
    purpose: str = Field(default="", max_length=200)


class SuccessV1(BaseModel):
    """How to know the goal was reached; at least one check is required."""

    model_config = ConfigDict(extra="forbid")

    url_contains: str | None = Field(default=None, max_length=300)
    text_present: str | None = Field(default=None, max_length=300)


class JourneyFileV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["accesspath_journey.v1"] = SCHEMA
    name: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=3, max_length=600)
    # Either a live address, or a folder in the repository served on a local port.
    start_url: str | None = Field(default=None, max_length=1000)
    site_dir: str | None = Field(default=None, max_length=300)
    start_path: str = Field(default="/", max_length=300)
    allowed_origins: list[str] = Field(default_factory=list, max_length=10)
    success: SuccessV1 | None = None
    completion_policy: dict[str, Any] | None = None
    type_values: dict[str, str] = Field(default_factory=dict, max_length=10)
    plan: list[PlanStepV1] = Field(default_factory=list, max_length=100)
    rules: dict[str, Any] = Field(default_factory=dict)
    max_steps: int = Field(default=40, ge=1, le=100)
    barrier_check: dict[str, Any] | None = None
    target_policy: dict[str, Any] | None = None
    # A saved browser session (Playwright storage state) for pages behind a sign-in.
    session: str | None = Field(default=None, max_length=300)
    # Staging only: allow form submissions on the journey's own origin (see docs).
    staging_writes: bool = False

    @model_validator(mode="after")
    def check(self) -> JourneyFileV1:
        if bool(self.start_url) == bool(self.site_dir):
            raise ValueError("give exactly one of start_url or site_dir")
        if self.start_url:
            parsed = urlparse(self.start_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("start_url must be an http or https address")
            if parsed.username or parsed.password:
                raise ValueError("do not put credentials in start_url")
        if not self.start_path.startswith("/"):
            raise ValueError("start_path must start with /")
        if self.completion_policy is None and not (
            self.success and (self.success.url_contains or self.success.text_present)
        ):
            raise ValueError("add a success check (url_contains or text_present)")
        RuleConfigV1.model_validate(self.rules or {}).validate_against(load_catalog())
        return self

    def completion(self) -> dict[str, Any]:
        if self.completion_policy is not None:
            return self.completion_policy
        signals = []
        if self.success and self.success.url_contains:
            signals.append(
                {
                    "id": "success_address",
                    "type": "url_contains",
                    "expected": self.success.url_contains,
                    "case_sensitive": False,
                }
            )
        if self.success and self.success.text_present:
            signals.append(
                {
                    "id": "success_text",
                    "type": "text_present",
                    "expected": " ".join(self.success.text_present.split()),
                    "case_sensitive": False,
                }
            )
        return {"signals": signals}


def _parse(text: str, suffix: str) -> Any:
    if suffix in {".yml", ".yaml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as error:
            raise ValueError(
                "YAML journeys need PyYAML (pip install pyyaml); or use JSON"
            ) from error
        return yaml.safe_load(text)
    return json.loads(text)


def load_journey(path: Path) -> JourneyFileV1:
    data = _parse(path.read_text(encoding="utf-8"), path.suffix.lower())
    if isinstance(data, dict) and data.get("schema_version") == "journey-manifest.v1":
        raise ValueError("this is a manifest; pick a journey with --key")
    return JourneyFileV1.model_validate(data)


def journey_from_manifest(path: Path, key: str, site_dir: str) -> JourneyFileV1:
    """A journey from a versioned fixture manifest (the demo and benchmark pages)."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    items = {item.get("key"): item for item in manifest.get("journeys", [])}
    if key not in items:
        raise ValueError(f"no journey {key!r} in {path.name}; keys: {', '.join(sorted(items))}")
    item = items[key]
    config = item.get("evaluation_config") or {}
    fallback = (config.get("planner") or {}).get("fallback") or {}
    return JourneyFileV1(
        name=item["name"],
        goal=item["goal"],
        site_dir=site_dir,
        start_path=item["start_path"],
        completion_policy=item["completion_policy"],
        type_values=fallback.get("synthetic_values", {}),
        plan=[PlanStepV1.model_validate(step) for step in fallback.get("actions", [])],
        barrier_check=config.get("barrier_check"),
        target_policy=config.get("target_policy"),
    )


EXAMPLE = {
    "schema_version": SCHEMA,
    "name": "Wikipedia search",
    "goal": "Use the search box to find and open the Web accessibility article.",
    "start_url": "https://en.wikipedia.org/wiki/Main_Page",
    "success": {"url_contains": "/wiki/Web_accessibility"},
    "type_values": {"text_to_type": "Web accessibility"},
    "rules": {"preset": "wcag22-aa", "fail_on": "serious"},
    "max_steps": 30,
}
