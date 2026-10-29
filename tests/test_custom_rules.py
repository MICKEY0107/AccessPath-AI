"""Team-defined rules built from the fixed custom checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from django.urls import reverse
from page_server import executor_for, serve_pages
from pydantic import ValidationError

from apps.journeys.models import Journey
from apps.runs.models import Run
from apps.runs.report import build_report
from engine.contracts import ActionKind, ProposedActionV1
from engine.rules import CustomRuleV1, RuleConfigV1, load_catalog, resolve_rules

PAGE = "<!doctype html><html lang='en'><head><title>t</title></head><body>{body}</body></html>"


def custom(check: str, selector: str, **extra) -> dict:
    return {
        "id": f"custom-{check.replace('_', '-')}",
        "title": f"Team rule {check}",
        "check": check,
        "selector": selector,
        "criterion": extra.pop("criterion", "2.1.1"),
        **extra,
    }


def run_with(tmp_path: Path, body: str, *rules: dict):
    rule_set = resolve_rules({"preset": "essential", "custom": list(rules)})
    with serve_pages({"/": PAGE.format(body=body)}) as origin:
        return executor_for(origin, tmp_path, rule_set=rule_set).run(
            [ProposedActionV1(action=ActionKind.TAB)]
        )


def findings(result, rule_id: str):
    return [item for item in result.findings if item.rule_id == rule_id]


def outcome(result, rule_id: str) -> str:
    return {item.rule_id: item.result for item in result.rule_results}[rule_id]


def test_custom_rules_validate_their_inputs() -> None:
    catalog = load_catalog()
    rule = CustomRuleV1.model_validate(custom("selector_named", ".icon", criterion="4.1.2"))
    assert rule.as_rule(catalog).wcag.criterion == "4.1.2"
    for bad in (
        custom("selector_named", "a { color: red }"),
        custom("selector_named", "a;b"),
        custom("selector_reachable_within", "#main"),  # needs max_tabs
        custom("run_javascript", "#x"),
        {**custom("selector_named", ".x"), "id": "not-custom"},
    ):
        with pytest.raises(ValidationError):
            CustomRuleV1.model_validate(bad)
    with pytest.raises(ValueError):
        RuleConfigV1.model_validate(
            {"custom": [custom("selector_named", ".x", criterion="1.4.3")]}
        ).validate_against(catalog)


def test_focusable_rule_reports_matches_that_tab_skips(tmp_path: Path) -> None:
    body = (
        "<button class='buy'>Buy now</button><button class='buy' tabindex='-1'>Buy later</button>"
    )
    result = run_with(tmp_path, body, custom("selector_focusable", ".buy"))
    [finding] = findings(result, "custom-selector-focusable")
    assert finding.status == "confirmed" and "Buy later" in finding.summary
    assert finding.title == "Team rule selector_focusable"
    assert outcome(result, "custom-selector-focusable") == "failed"


def test_named_rule_reports_unnamed_matches_only(tmp_path: Path) -> None:
    body = (
        "<button class='icon'><svg aria-hidden='true' width='10' height='10'></svg></button>"
        "<button class='icon' aria-label='Close'>x</button>"
    )
    result = run_with(tmp_path, body, custom("selector_named", ".icon", criterion="4.1.2"))
    [finding] = findings(result, "custom-selector-named")
    assert finding.wcag_criterion == "4.1.2"
    assert finding.occurrences == 1


def test_reachable_within_counts_tab_presses(tmp_path: Path) -> None:
    links = "".join(f"<a href='/p{index}'>Link {index}</a>" for index in range(6))
    body = f"<nav>{links}</nav><main><button id='checkout'>Checkout</button></main>"
    late = run_with(
        tmp_path,
        body,
        custom("selector_reachable_within", "#checkout", max_tabs=3, criterion="2.4.1"),
    )
    [finding] = findings(late, "custom-selector-reachable-within")
    assert "takes 7 Tab presses" in finding.summary
    early = run_with(
        tmp_path, body, custom("selector_reachable_within", "main", max_tabs=7, criterion="2.4.1")
    )
    assert findings(early, "custom-selector-reachable-within") == []
    assert outcome(early, "custom-selector-reachable-within") == "passed"


def test_absent_rule_and_unmatched_selector(tmp_path: Path) -> None:
    body = "<div onclick='go()' class='fake-button'>Go</div><button>Real</button>"
    result = run_with(
        tmp_path,
        body,
        custom("selector_absent", "div[onclick]", criterion="4.1.2"),
        {**custom("selector_focusable", ".does-not-exist"), "id": "custom-unmatched"},
    )
    [finding] = findings(result, "custom-selector-absent")
    assert "1 visible element match" in finding.summary
    assert outcome(result, "custom-unmatched") == "not_applicable"


def test_an_invalid_selector_is_not_checked_rather_than_passed(tmp_path: Path) -> None:
    result = run_with(
        tmp_path, "<button>Ok</button>", custom("selector_focusable", "button:::nope")
    )
    rows = {item.rule_id: item for item in result.rule_results}
    assert rows["custom-selector-focusable"].result == "not_checked"
    assert "not valid" in rows["custom-selector-focusable"].detail


@pytest.mark.django_db
def test_rules_page_adds_keeps_and_removes_custom_rules(client) -> None:
    journey = Journey.objects.create(
        name="Shop",
        goal="Buy a thing by keyboard.",
        start_url="https://example.org/",
        allowed_origins=["https://example.org"],
        completion_policy={},
        evaluation_config={},
    )
    base = {"preset": "essential", "fail_on": "serious"}
    for rule_id in load_catalog().preset("essential").rules:
        base[f"enabled-{rule_id}"] = "on"
    url = reverse("runs:save_rules", args=[journey.id])
    response = client.post(
        url,
        {
            **base,
            "new-custom-title": "Checkout reachable quickly",
            "new-custom-check": "selector_reachable_within",
            "new-custom-selector": "#checkout",
            "new-custom-max": "5",
            "new-custom-severity": "critical",
        },
    )
    assert response.status_code == 302
    journey.refresh_from_db()
    [rule] = RuleConfigV1.model_validate(journey.rule_config).custom
    assert rule.id == "custom-checkout-reachable-quickly"
    assert rule.criterion == "2.4.1" and rule.max_tabs == 5 and rule.severity == "critical"

    page = client.get(reverse("runs:rules"), {"journey": journey.id}).content.decode()
    assert "Checkout reachable quickly" in page and "within 5 Tab presses" in page

    import json

    kept = {
        **base,
        "keep-custom": "0",
        "custom-0": json.dumps(rule.model_dump(mode="json")),
        "new-custom-title": "Checkout reachable quickly",
        "new-custom-check": "selector_named",
        "new-custom-selector": ".icon",
    }
    client.post(url, kept)
    journey.refresh_from_db()
    ids = [item.id for item in RuleConfigV1.model_validate(journey.rule_config).custom]
    assert ids == ["custom-checkout-reachable-quickly", "custom-checkout-reachable-quickly-2"]

    client.post(url, base)  # neither kept
    journey.refresh_from_db()
    assert RuleConfigV1.model_validate(journey.rule_config).custom == []

    bad = client.post(
        url,
        {
            **base,
            "new-custom-title": "Broken",
            "new-custom-check": "selector_named",
            "new-custom-selector": "a{}",
        },
    )
    assert bad.status_code == 400 and "not valid" in bad.content.decode()


@pytest.mark.django_db
def test_report_shows_custom_rule_results() -> None:
    rule = custom("selector_named", ".icon", criterion="4.1.2")
    journey = Journey.objects.create(
        name="Shop",
        goal="Buy a thing by keyboard.",
        start_url="https://example.org/",
        allowed_origins=["https://example.org"],
        completion_policy={},
        evaluation_config={},
    )
    run = Run.objects.create(
        journey=journey,
        planner_provider="fixture",
        status="succeeded",
        outcome="completed",
        planner_metadata={"rules": resolve_rules({"custom": [rule]}).to_metadata()},
        rule_results=[
            {"rule_id": rule["id"], "result": "passed", "detail": "", "finding_count": 0}
        ],
    )
    rows = build_report(run)["rule_results"]
    assert [row["rule"].title for row in rows] == ["Team rule selector_named"]


def test_focus_styling_classes_do_not_cause_false_failures(tmp_path: Path) -> None:
    script = (
        "<script>document.querySelectorAll('a,button').forEach((element) => {"
        "element.addEventListener('focus', () => element.classList.add('is-focused'));"
        "element.addEventListener('blur', () => element.classList.remove('is-focused'));"
        "});</script>"
    )
    body = "<a href='/a'>One</a><button class='go'>Buy</button>" + script
    result = run_with(
        tmp_path,
        body,
        custom("selector_focusable", "button"),
        custom("selector_reachable_within", ".go", max_tabs=2, criterion="2.4.1"),
    )
    assert findings(result, "custom-selector-focusable") == []
    assert findings(result, "custom-selector-reachable-within") == []
    assert outcome(result, "custom-selector-reachable-within") == "passed"


def test_every_match_is_checked_and_composite_items_are_not_flagged(tmp_path: Path) -> None:
    buttons = "".join(f"<button class='b'>B{index}</button>" for index in range(11))
    buttons += "<button class='b' tabindex='-1'>Skipped</button>"
    tabs = (
        "<div role='tablist'><button role='tab' class='t' aria-selected='true'>A</button>"
        "<button role='tab' class='t' tabindex='-1'>B</button></div>"
    )
    result = run_with(
        tmp_path,
        buttons + tabs,
        custom("selector_focusable", ".b"),
        {**custom("selector_focusable", ".t"), "id": "custom-tabs"},
    )
    [finding] = findings(result, "custom-selector-focusable")
    assert "Skipped" in finding.summary
    assert findings(result, "custom-tabs") == []


def test_a_disabled_team_rule_does_not_run_and_severity_overrides_apply(tmp_path: Path) -> None:
    rule = custom("selector_absent", "button", criterion="4.1.2")
    rule_set = resolve_rules(
        {
            "preset": "essential",
            "custom": [rule],
            "disabled": [{"id": rule["id"], "reason": "Not for this page"}],
        }
    )
    assert not rule_set.is_active(rule["id"])
    with serve_pages({"/": PAGE.format(body="<button>Go</button>")}) as origin:
        result = executor_for(origin, tmp_path, rule_set=rule_set).run(
            [ProposedActionV1(action=ActionKind.TAB)]
        )
    assert findings(result, rule["id"]) == []
    assert outcome(result, rule["id"]) == "disabled"
    overridden = resolve_rules({"custom": [rule], "severity": {rule["id"]: "minor"}})
    assert overridden.get(rule["id"]).severity == "minor"


@pytest.mark.django_db
def test_removing_a_team_rule_also_removes_its_ignores(client) -> None:
    import json
    from datetime import date, timedelta

    rule = CustomRuleV1.model_validate(custom("selector_named", ".icon", criterion="4.1.2"))
    journey = Journey.objects.create(
        name="Shop",
        goal="Buy a thing by keyboard.",
        start_url="https://example.org/",
        allowed_origins=["https://example.org"],
        completion_policy={},
        evaluation_config={},
        rule_config={"preset": "essential", "custom": [rule.model_dump(mode="json")]},
    )
    data = {
        "preset": "essential",
        "fail_on": "serious",
        "keep-ignore": "0",
        "ignore-0-id": rule.id,
        "ignore-0-match": ".icon",
        "ignore-0-reason": "Ticket 1",
        "ignore-0-until": (date.today() + timedelta(days=9)).isoformat(),
    }
    for rule_id in load_catalog().preset("essential").rules:
        data[f"enabled-{rule_id}"] = "on"
    response = client.post(reverse("runs:save_rules", args=[journey.id]), data)
    assert response.status_code == 302
    journey.refresh_from_db()
    config = RuleConfigV1.model_validate(journey.rule_config)
    assert config.custom == [] and config.ignores == []
    assert json.dumps(journey.rule_config)
