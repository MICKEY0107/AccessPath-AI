"""Versioned accessibility rule catalog, presets, and per-journey rule settings.

The catalog ships with the code (``rules/catalog.json``) and is reviewed by people,
so a changed web page can never change which rules run or how they are described.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

Severity = Literal["critical", "serious", "moderate", "minor"]
SEVERITY_ORDER: dict[str, int] = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}
RULE_ID_PATTERN = r"^[a-z][a-z0-9-]{1,63}$"
CATALOG_PATH = Path(__file__).resolve().parents[1] / "rules" / "catalog.json"


class WcagReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: str = Field(pattern=r"^\d\.\d\.\d{1,2}$")
    name: str = Field(min_length=1, max_length=80)
    level: Literal["A", "AA", "AAA"]
    url: HttpUrl


class ActRuleReferenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]{6}$")
    name: str = Field(min_length=1, max_length=160)
    url: HttpUrl


class RuleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RULE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    wcag: WcagReferenceV1
    act_rules: list[ActRuleReferenceV1] = Field(default_factory=list)
    checks: list[str] = Field(min_length=1)
    default_severity: Severity
    summary: str = Field(min_length=1, max_length=400)
    fix_hints: list[str] = Field(min_length=1)
    code_patterns: list[str] = Field(default_factory=list)
    advisory: bool = False


class PresetV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RULE_ID_PATTERN)
    label: str = Field(min_length=1, max_length=60)
    description: str = Field(min_length=1, max_length=300)
    rules: list[str] = Field(min_length=1)
    axe_tags: list[str] = Field(default_factory=list)


class RuleCatalogV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rule_catalog.v1"]
    catalog_version: str = Field(min_length=1, max_length=32)
    reviewed: date
    sources: dict[str, HttpUrl]
    rules: list[RuleV1] = Field(min_length=1)
    presets: list[PresetV1] = Field(min_length=1)
    default_preset: str

    @model_validator(mode="after")
    def references_are_consistent(self) -> RuleCatalogV1:
        rule_ids = [rule.id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule ids must be unique")
        preset_ids = [preset.id for preset in self.presets]
        if len(preset_ids) != len(set(preset_ids)):
            raise ValueError("preset ids must be unique")
        for preset in self.presets:
            unknown = set(preset.rules) - set(rule_ids)
            if unknown:
                raise ValueError(f"preset {preset.id} names unknown rules: {sorted(unknown)}")
        if self.default_preset not in preset_ids:
            raise ValueError("default_preset must name a preset")
        return self

    def rule(self, rule_id: str) -> RuleV1:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)

    def preset(self, preset_id: str) -> PresetV1:
        for preset in self.presets:
            if preset.id == preset_id:
                return preset
        raise KeyError(preset_id)


@lru_cache(maxsize=4)
def _load_catalog(path: str) -> RuleCatalogV1:
    return RuleCatalogV1.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_catalog(path: Path | None = None) -> RuleCatalogV1:
    """Load and validate the shipped catalog; cached because it never changes at runtime."""
    return _load_catalog(str(path or CATALOG_PATH))


class DisabledRuleV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RULE_ID_PATTERN)
    reason: str = Field(min_length=3, max_length=240)


class RuleIgnoreV1(BaseModel):
    """A known issue accepted for now: it stays visible but does not fail the run."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=RULE_ID_PATTERN)
    # Matches a finding whose element selector or accessible name contains this text.
    match: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=240)
    until: date


class RuleConfigV1(BaseModel):
    """Per-journey rule settings chosen on the Rules page."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rule_config.v1"] = "rule_config.v1"
    preset: str = "wcag22-aa"
    fail_on: Severity = "serious"
    disabled: list[DisabledRuleV1] = Field(default_factory=list, max_length=20)
    severity: dict[str, Severity] = Field(default_factory=dict, max_length=20)
    ignores: list[RuleIgnoreV1] = Field(default_factory=list, max_length=50)

    @field_validator("severity")
    @classmethod
    def severity_keys_are_rule_ids(cls, values: dict[str, Severity]) -> dict[str, Severity]:
        import re

        if any(not re.match(RULE_ID_PATTERN, key) for key in values):
            raise ValueError("severity overrides must be keyed by rule id")
        return values

    def validate_against(self, catalog: RuleCatalogV1) -> RuleConfigV1:
        """Refuse settings that name presets or rules the catalog does not have."""
        catalog.preset(self.preset)
        known = {rule.id for rule in catalog.rules}
        named = (
            {item.id for item in self.disabled}
            | set(self.severity)
            | {item.id for item in self.ignores}
        )
        unknown = named - known
        if unknown:
            raise ValueError(f"unknown rule ids: {sorted(unknown)}")
        return self


@dataclass(frozen=True)
class ActiveRule:
    rule: RuleV1
    severity: str

    @property
    def id(self) -> str:
        return self.rule.id


@dataclass
class ActiveRuleSet:
    """The rules one run applies, after the preset, disables and overrides."""

    catalog_version: str
    preset: str
    fail_on: str
    rules: list[ActiveRule]
    disabled: dict[str, str]
    axe_tags: list[str]
    ignores: list[RuleIgnoreV1] = field(default_factory=list)
    expired_ignores: list[RuleIgnoreV1] = field(default_factory=list)

    def get(self, rule_id: str) -> ActiveRule | None:
        return next((item for item in self.rules if item.id == rule_id), None)

    def is_active(self, rule_id: str) -> bool:
        return self.get(rule_id) is not None

    def ignore_for(self, rule_id: str, *texts: str | None) -> RuleIgnoreV1 | None:
        haystacks = [text.lower() for text in texts if text]
        for ignore in self.ignores:
            if ignore.id == rule_id and any(ignore.match.lower() in hay for hay in haystacks):
                return ignore
        return None

    def fails_run(self, severity: str) -> bool:
        return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER[self.fail_on]

    def to_metadata(self) -> dict[str, object]:
        return {
            "catalog_version": self.catalog_version,
            "preset": self.preset,
            "fail_on": self.fail_on,
            "rules": {item.id: item.severity for item in self.rules},
            "disabled": self.disabled,
            "axe_tags": self.axe_tags,
            "ignores": [item.model_dump(mode="json") for item in self.ignores],
            "expired_ignores": [item.model_dump(mode="json") for item in self.expired_ignores],
        }


def resolve_rules(
    config: dict | RuleConfigV1 | None,
    *,
    today: date | None = None,
    catalog: RuleCatalogV1 | None = None,
) -> ActiveRuleSet:
    """Apply a journey's settings to its preset; missing settings mean the default preset."""
    catalog = catalog or load_catalog()
    if isinstance(config, RuleConfigV1):
        settings = config
    else:
        settings = RuleConfigV1.model_validate(config or {"preset": catalog.default_preset})
    settings.validate_against(catalog)
    preset = catalog.preset(settings.preset)
    disabled = {item.id: item.reason for item in settings.disabled}
    rules = [
        ActiveRule(rule=rule, severity=settings.severity.get(rule.id, rule.default_severity))
        for rule in (catalog.rule(rule_id) for rule_id in preset.rules)
        if rule.id not in disabled
    ]
    today = today or date.today()
    current = [item for item in settings.ignores if item.until >= today]
    expired = [item for item in settings.ignores if item.until < today]
    return ActiveRuleSet(
        catalog_version=catalog.catalog_version,
        preset=preset.id,
        fail_on=settings.fail_on,
        rules=rules,
        disabled=disabled,
        axe_tags=list(preset.axe_tags),
        ignores=current,
        expired_ignores=expired,
    )
