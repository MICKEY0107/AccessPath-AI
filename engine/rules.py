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


CustomCheck = Literal[
    "selector_focusable", "selector_named", "selector_reachable_within", "selector_absent"
]
CUSTOM_RULE_ID_PATTERN = r"^custom-[a-z0-9-]{1,56}$"

# The only checks a custom rule can use. Each takes a CSS selector (and the reachable
# check a number), so a rule can be tightened for one product without running code.
CUSTOM_CHECKS: dict[str, dict[str, str]] = {
    "selector_focusable": {
        "label": "Must be reachable with Tab",
        "help": "Every visible element matching the selector must be a stop in the Tab order.",
        "criterion": "2.1.1",
        "fix": 'Use a native control, or remove tabindex="-1" from the matching elements.',
    },
    "selector_named": {
        "label": "Must have an accessible name",
        "help": "Every visible element matching the selector must have a name a screen "
        "reader announces.",
        "criterion": "4.1.2",
        "fix": "Give the matching elements visible text, aria-label or aria-labelledby.",
    },
    "selector_reachable_within": {
        "label": "Must be reached within N Tab presses",
        "help": "The first visible element matching the selector must be reached from the top "
        "of the page within the given number of Tab presses.",
        "criterion": "2.4.1",
        "fix": "Add a skip link to it, or move it earlier in the page source.",
    },
    "selector_absent": {
        "label": "Must not appear",
        "help": "No visible element may match the selector (for example a banned pattern).",
        "criterion": "4.1.2",
        "fix": "Replace the matching pattern with the accessible one your team agreed.",
    },
}


class CustomRuleV1(BaseModel):
    """A team's own rule, built from one of the fixed checks above; never runs code."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=CUSTOM_RULE_ID_PATTERN)
    title: str = Field(min_length=3, max_length=120)
    check: CustomCheck
    selector: str = Field(min_length=1, max_length=200)
    max_tabs: int | None = Field(default=None, ge=1, le=60)
    criterion: str = Field(pattern=r"^\d\.\d\.\d{1,2}$")
    severity: Severity = "serious"
    fix_hint: str = Field(default="", max_length=240)

    @field_validator("selector")
    @classmethod
    def selector_is_one_line(cls, value: str) -> str:
        value = value.strip()
        if not value or any(char in value for char in "\n\r{};"):
            raise ValueError("a selector is one line without braces or semicolons")
        return value

    @model_validator(mode="after")
    def reachable_needs_a_number(self) -> CustomRuleV1:
        if self.check == "selector_reachable_within" and self.max_tabs is None:
            raise ValueError("say within how many Tab presses")
        if self.check != "selector_reachable_within":
            self.max_tabs = None
        return self

    def describe(self) -> str:
        if self.check == "selector_focusable":
            return f"Every visible “{self.selector}” must be reachable with Tab."
        if self.check == "selector_named":
            return f"Every visible “{self.selector}” must have an accessible name."
        if self.check == "selector_reachable_within":
            return (
                f"The first “{self.selector}” must be reached within {self.max_tabs} Tab presses."
            )
        return f"No visible element may match “{self.selector}”."

    def as_rule(self, catalog: RuleCatalogV1) -> RuleV1:
        """The custom rule in catalog shape, borrowing the WCAG reference it names."""
        wcag = next(
            (rule.wcag for rule in catalog.rules if rule.wcag.criterion == self.criterion), None
        )
        if wcag is None:
            raise ValueError(f"no catalog rule covers WCAG {self.criterion}")
        return RuleV1(
            id=self.id,
            title=self.title,
            wcag=wcag,
            checks=[self.check],
            default_severity=self.severity,
            summary=self.describe(),
            fix_hints=[self.fix_hint or CUSTOM_CHECKS[self.check]["fix"]],
        )


def custom_rule_id(title: str, taken: set[str]) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "rule"
    candidate, number = f"custom-{slug}", 2
    while candidate in taken:
        candidate, number = f"custom-{slug}-{number}", number + 1
    return candidate


def wcag_choices(catalog: RuleCatalogV1) -> list[tuple[str, str]]:
    """The WCAG criteria a custom rule may name: those the catalog covers."""
    seen: dict[str, str] = {}
    for rule in catalog.rules:
        seen.setdefault(rule.wcag.criterion, f"{rule.wcag.criterion} {rule.wcag.name}")
    return sorted(seen.items(), key=lambda item: [int(part) for part in item[0].split(".")])


class RuleConfigV1(BaseModel):
    """Per-journey rule settings chosen on the Rules page."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rule_config.v1"] = "rule_config.v1"
    preset: str = "wcag22-aa"
    fail_on: Severity = "serious"
    disabled: list[DisabledRuleV1] = Field(default_factory=list, max_length=20)
    severity: dict[str, Severity] = Field(default_factory=dict, max_length=20)
    ignores: list[RuleIgnoreV1] = Field(default_factory=list, max_length=50)
    custom: list[CustomRuleV1] = Field(default_factory=list, max_length=20)

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
        custom_ids = [item.id for item in self.custom]
        if len(custom_ids) != len(set(custom_ids)):
            raise ValueError("custom rule ids must be unique")
        for item in self.custom:
            item.as_rule(catalog)
        unknown = named - known - set(custom_ids)
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
    custom: list[CustomRuleV1] = field(default_factory=list)

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
            "custom": [item.model_dump(mode="json") for item in self.custom],
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
    rules += [
        ActiveRule(
            rule=item.as_rule(catalog), severity=settings.severity.get(item.id, item.severity)
        )
        for item in settings.custom
        if item.id not in disabled
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
        custom=list(settings.custom),
    )


def rules_for_metadata(
    metadata: dict | None, catalog: RuleCatalogV1 | None = None
) -> dict[str, RuleV1]:
    """Catalog rules plus the custom rules a run recorded, keyed by id (for reports)."""
    catalog = catalog or load_catalog()
    rules = {rule.id: rule for rule in catalog.rules}
    for raw in (metadata or {}).get("custom") or []:
        try:
            custom = CustomRuleV1.model_validate(raw)
            rules[custom.id] = custom.as_rule(catalog)
        except (ValueError, TypeError):
            continue
    return rules
