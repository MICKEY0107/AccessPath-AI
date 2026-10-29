"""Turn the Rules page form into validated per-journey rule settings."""

from __future__ import annotations

from datetime import date

from django.http import QueryDict
from pydantic import ValidationError

from engine.rules import RuleCatalogV1, RuleConfigV1, load_catalog

SEVERITY_CHOICES = ["critical", "serious", "moderate", "minor"]


class RuleSettingsError(ValueError):
    """A form value the Rules page cannot save; the message is shown to the person."""


def current_config(rule_config: dict, catalog: RuleCatalogV1 | None = None) -> RuleConfigV1:
    catalog = catalog or load_catalog()
    try:
        return RuleConfigV1.model_validate(rule_config or {"preset": catalog.default_preset})
    except ValidationError:
        # Stored settings that no longer validate fall back to the default preset.
        return RuleConfigV1(preset=catalog.default_preset)


def rule_rows(config: RuleConfigV1, catalog: RuleCatalogV1 | None = None) -> list[dict]:
    """One row per catalog rule, saying whether the chosen preset runs it."""
    catalog = catalog or load_catalog()
    preset = catalog.preset(config.preset)
    disabled = {item.id: item.reason for item in config.disabled}
    rows = []
    for rule in catalog.rules:
        rows.append(
            {
                "rule": rule,
                "in_preset": rule.id in preset.rules,
                "enabled": rule.id in preset.rules and rule.id not in disabled,
                "disabled_reason": disabled.get(rule.id, ""),
                "severity": config.severity.get(rule.id, rule.default_severity),
                "severity_overridden": rule.id in config.severity,
            }
        )
    return rows


def config_from_form(data: QueryDict, catalog: RuleCatalogV1 | None = None) -> RuleConfigV1:
    """Build settings from the posted form; every rule id must exist in the catalog."""
    catalog = catalog or load_catalog()
    preset_id = data.get("preset", catalog.default_preset)
    try:
        preset = catalog.preset(preset_id)
    except KeyError as error:
        raise RuleSettingsError("Choose one of the listed presets.") from error

    disabled = []
    severity = {}
    for rule in catalog.rules:
        if rule.id in preset.rules and data.get(f"enabled-{rule.id}") != "on":
            reason = data.get(f"reason-{rule.id}", "").strip()
            if len(reason) < 3:
                raise RuleSettingsError(
                    f"Say why “{rule.title}” is turned off, so the reason shows in review."
                )
            disabled.append({"id": rule.id, "reason": reason[:240]})
        chosen = data.get(f"severity-{rule.id}", rule.default_severity)
        if chosen not in SEVERITY_CHOICES:
            raise RuleSettingsError("Choose a listed severity.")
        if chosen != rule.default_severity:
            severity[rule.id] = chosen

    ignores = []
    for index in data.getlist("keep-ignore"):
        prefix = f"ignore-{index}-"
        ignores.append(
            {
                "id": data.get(prefix + "id", ""),
                "match": data.get(prefix + "match", ""),
                "reason": data.get(prefix + "reason", ""),
                "until": data.get(prefix + "until", ""),
            }
        )
    new_match = data.get("new-ignore-match", "").strip()
    if new_match:
        until = data.get("new-ignore-until", "").strip()
        try:
            until_date = date.fromisoformat(until)
        except ValueError as error:
            raise RuleSettingsError("Give the ignore an expiry date (YYYY-MM-DD).") from error
        if until_date < date.today():
            raise RuleSettingsError("An ignore's expiry date must be today or later.")
        ignores.append(
            {
                "id": data.get("new-ignore-id", ""),
                "match": new_match,
                "reason": data.get("new-ignore-reason", "").strip(),
                "until": until,
            }
        )

    try:
        config = RuleConfigV1.model_validate(
            {
                "preset": preset.id,
                "fail_on": data.get("fail_on", "serious"),
                "disabled": disabled,
                "severity": severity,
                "ignores": ignores,
            }
        )
        return config.validate_against(catalog)
    except (ValidationError, ValueError) as error:
        raise RuleSettingsError(
            "Some rule settings were not valid. Check each ignore has a rule, a match text, "
            "a reason of at least 3 characters and an expiry date."
        ) from error
