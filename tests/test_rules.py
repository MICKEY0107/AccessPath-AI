"""Rule catalog, presets, per-journey settings, and the Rules page."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse

from apps.journeys.models import Journey
from engine.rules import RuleConfigV1, load_catalog, resolve_rules


def test_catalog_loads_and_every_rule_cites_wcag_and_fix_hints() -> None:
    catalog = load_catalog()
    assert catalog.schema_version == "rule_catalog.v1"
    criteria = {rule.wcag.criterion for rule in catalog.rules}
    assert {"2.1.1", "2.1.2", "2.4.1", "2.4.3", "2.4.7", "2.4.11", "3.2.1", "4.1.2"} <= criteria
    for rule in catalog.rules:
        assert str(rule.wcag.url).startswith("https://www.w3.org/WAI/WCAG22/Understanding/")
        assert rule.fix_hints
        for act in rule.act_rules:
            assert str(act.url).startswith("https://www.w3.org/WAI/standards-guidelines/act/rules/")
            assert act.id in str(act.url)


def test_presets_grow_from_essential_to_strict() -> None:
    essential = resolve_rules({"preset": "essential"})
    aa = resolve_rules({"preset": "wcag22-aa"})
    strict = resolve_rules({"preset": "strict"})
    ids = lambda rule_set: {rule.id for rule in rule_set.rules}  # noqa: E731
    assert ids(essential) < ids(aa) < ids(strict)
    assert ids(essential) == {"keyboard-operable", "no-keyboard-trap", "focus-order", "name-role-value"}
    assert "focus-appearance" in ids(strict) and "focus-appearance" not in ids(aa)
    assert essential.axe_tags == []
    assert "wcag22aa" in aa.axe_tags


def test_missing_settings_use_the_default_preset() -> None:
    rule_set = resolve_rules({})
    assert rule_set.preset == load_catalog().default_preset
    assert rule_set.fail_on == "serious"


def test_disable_override_and_ignores_apply() -> None:
    today = date(2026, 10, 29)
    rule_set = resolve_rules(
        {
            "preset": "wcag22-aa",
            "disabled": [{"id": "bypass-blocks", "reason": "Single-page tool"}],
            "severity": {"focus-visible": "critical"},
            "ignores": [
                {"id": "name-role-value", "match": ".toggle", "reason": "A11Y-12", "until": "2027-01-31"},
                {"id": "name-role-value", "match": ".old", "reason": "Expired one", "until": "2026-01-01"},
            ],
        },
        today=today,
    )
    assert not rule_set.is_active("bypass-blocks")
    assert rule_set.disabled == {"bypass-blocks": "Single-page tool"}
    assert rule_set.get("focus-visible").severity == "critical"
    assert rule_set.ignore_for("name-role-value", "ul.todo-list > li > input.toggle") is not None
    assert rule_set.ignore_for("name-role-value", "input.old") is None
    assert [item.match for item in rule_set.expired_ignores] == [".old"]
    assert rule_set.ignore_for("focus-visible", ".toggle") is None


def test_fail_on_threshold() -> None:
    rule_set = resolve_rules({"preset": "essential", "fail_on": "serious"})
    assert rule_set.fails_run("critical") and rule_set.fails_run("serious")
    assert not rule_set.fails_run("moderate")


def test_unknown_rule_ids_are_refused() -> None:
    with pytest.raises(ValueError, match="unknown rule ids"):
        resolve_rules({"preset": "essential", "severity": {"made-up-rule": "minor"}})
    with pytest.raises(KeyError):
        RuleConfigV1(preset="nope").validate_against(load_catalog())


def _journey() -> Journey:
    return Journey.objects.create(
        name="Rules test journey",
        goal="Reach the confirmation page by keyboard.",
        start_url="https://example.org/",
        allowed_origins=["https://example.org"],
        completion_policy={},
        evaluation_config={},
    )


@pytest.mark.django_db
def test_rules_page_lists_the_catalog(client) -> None:
    journey = _journey()
    response = client.get(reverse("runs:rules"), {"journey": journey.id})
    assert response.status_code == 200
    body = response.content.decode()
    assert "Every control works with the keyboard" in body
    assert "2.4.7 Focus Visible" in body
    assert "WCAG 2.2 AA" in body


@pytest.mark.django_db
def test_saving_rules_stores_a_valid_config(client) -> None:
    journey = _journey()
    catalog = load_catalog()
    data = {"preset": "wcag22-aa", "fail_on": "critical"}
    for rule_id in catalog.preset("wcag22-aa").rules:
        if rule_id != "bypass-blocks":
            data[f"enabled-{rule_id}"] = "on"
    data["reason-bypass-blocks"] = "Single-page tool, no repeated navigation"
    data["severity-focus-visible"] = "critical"
    data["new-ignore-id"] = "name-role-value"
    data["new-ignore-match"] = ".toggle"
    data["new-ignore-reason"] = "Ticket A11Y-12"
    data["new-ignore-until"] = (date.today() + timedelta(days=30)).isoformat()
    response = client.post(reverse("runs:save_rules", args=[journey.id]), data)
    assert response.status_code == 302
    journey.refresh_from_db()
    config = RuleConfigV1.model_validate(journey.rule_config)
    assert config.fail_on == "critical"
    assert [item.id for item in config.disabled] == ["bypass-blocks"]
    assert config.severity == {"focus-visible": "critical"}
    assert config.ignores[0].match == ".toggle"


@pytest.mark.django_db
def test_turning_a_rule_off_needs_a_reason(client) -> None:
    journey = _journey()
    data = {"preset": "essential", "fail_on": "serious"}
    response = client.post(reverse("runs:save_rules", args=[journey.id]), data)
    assert response.status_code == 400
    journey.refresh_from_db()
    assert journey.rule_config == {}
    assert "Say why" in response.content.decode()


@pytest.mark.django_db
def test_an_ignore_needs_a_future_expiry(client) -> None:
    journey = _journey()
    data = {"preset": "essential", "fail_on": "serious"}
    for rule_id in load_catalog().preset("essential").rules:
        data[f"enabled-{rule_id}"] = "on"
    data["new-ignore-id"] = "name-role-value"
    data["new-ignore-match"] = ".toggle"
    data["new-ignore-reason"] = "Old ticket"
    data["new-ignore-until"] = "2020-01-01"
    response = client.post(reverse("runs:save_rules", args=[journey.id]), data)
    assert response.status_code == 400
    assert "expiry date" in response.content.decode()
