"""Turn the Rules page form into validated per-journey rule settings."""

from __future__ import annotations

import json
from datetime import date

from django.http import QueryDict
from pydantic import ValidationError

from engine.rules import (
    CUSTOM_CHECKS,
    CustomRuleV1,
    RuleCatalogV1,
    RuleConfigV1,
    custom_rule_id,
    load_catalog,
)

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

    custom = _custom_rules_from_form(data, catalog)
    # Ignores for a team rule that was just removed go with it.
    known = {rule.id for rule in catalog.rules} | {item["id"] for item in custom}
    ignores = [item for item in ignores if item.get("id") in known]

    try:
        config = RuleConfigV1.model_validate(
            {
                "preset": preset.id,
                "fail_on": data.get("fail_on", "serious"),
                "disabled": disabled,
                "severity": severity,
                "ignores": ignores,
                "custom": custom,
            }
        )
        return config.validate_against(catalog)
    except (ValidationError, ValueError) as error:
        raise RuleSettingsError(
            "Some rule settings were not valid. Check each ignore has a rule, a match text, "
            "a reason of at least 3 characters and an expiry date."
        ) from error


def _custom_rules_from_form(data: QueryDict, catalog: RuleCatalogV1) -> list[dict]:
    """Kept custom rules (posted back as JSON) plus a new one from the add form."""
    rules: list[dict] = []
    for index in data.getlist("keep-custom"):
        try:
            rules.append(
                CustomRuleV1.model_validate(
                    json.loads(data.get(f"custom-{index}", ""))
                ).model_dump()
            )
        except (ValueError, TypeError, ValidationError) as error:
            raise RuleSettingsError(
                "A saved custom rule could not be read; add it again."
            ) from error
    title = data.get("new-custom-title", "").strip()
    selector = data.get("new-custom-selector", "").strip()
    if not title and not selector:
        return rules
    if not title or not selector:
        raise RuleSettingsError("A custom rule needs a name and a CSS selector.")
    check = data.get("new-custom-check", "")
    if check not in CUSTOM_CHECKS:
        raise RuleSettingsError("Choose one of the listed checks for the custom rule.")
    criterion = data.get("new-custom-criterion", "").strip() or CUSTOM_CHECKS[check]["criterion"]
    max_tabs = data.get("new-custom-max", "").strip()
    if check == "selector_reachable_within" and not max_tabs.isdigit():
        raise RuleSettingsError(
            "Say within how many Tab presses (1 to 60) the element must be reached."
        )
    try:
        rule = CustomRuleV1(
            id=custom_rule_id(title, {item["id"] for item in rules}),
            title=title,
            check=check,
            selector=selector,
            max_tabs=int(max_tabs) if check == "selector_reachable_within" else None,
            criterion=criterion,
            severity=data.get("new-custom-severity", "serious"),
            fix_hint=data.get("new-custom-fix", "").strip(),
        )
        rule.as_rule(catalog)
    except (ValidationError, ValueError) as error:
        raise RuleSettingsError(
            "The custom rule is not valid. Use a one-line CSS selector (no braces or semicolons), "
            "a name of at least 3 characters and, for “within N Tab presses”, a number from "
            "1 to 60."
        ) from error
    rules.append(rule.model_dump())
    return rules


def custom_rows(config: RuleConfigV1) -> list[dict]:
    return [
        {
            "index": index,
            "rule": item,
            "json": json.dumps(item.model_dump(mode="json")),
            "check_label": CUSTOM_CHECKS[item.check]["label"],
            "describe": item.describe(),
        }
        for index, item in enumerate(config.custom)
    ]
