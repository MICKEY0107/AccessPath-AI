"""A run may blame the website only when a deterministic re-check confirms the barrier."""

from __future__ import annotations

from pathlib import Path

from page_server import executor_for, serve_pages

from engine.contracts import ActionKind, PlannerObservationV1, ProposedActionV1
from engine.findings import FindingCollector
from engine.rules import resolve_rules

PAGE = "<!doctype html><html lang='en'><head><title>t</title></head><body>{}</body></html>"


def tab(hint: str = "") -> ProposedActionV1:
    return ProposedActionV1(action=ActionKind.TAB, target_hint=hint)


def test_visible_control_skipped_by_tab_is_a_confirmed_barrier(tmp_path: Path) -> None:
    page = PAGE.format(
        "<a href='/help'>Help</a>"
        "<div class='pay' style='cursor:pointer;padding:8px' "
        "onclick=\"document.body.dataset.paid='1'\">Pay now</div>"
    )
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path).run([tab("Pay now"), tab("Pay now")])
    assert result.outcome == "blocked"
    assert result.terminal_reason == "KEYBOARD_TARGET_NOT_REACHABLE"
    assert result.failure_kind == "site_barrier"
    [finding] = result.findings
    assert finding.rule_id == "keyboard-operable"
    assert finding.wcag_criterion == "2.1.1"
    assert finding.status == "confirmed"
    assert finding.element.name == "Pay now"
    assert "not focusable" in finding.summary


def test_control_that_only_works_with_a_mouse_is_confirmed(tmp_path: Path) -> None:
    page = PAGE.format(
        "<span role='button' tabindex='0' "
        "onclick=\"document.getElementById('out').textContent='Saved'\">Save draft</span>"
        "<p id='out'></p>"
    )
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path).run([tab("Save draft")])
    assert result.outcome == "blocked"
    assert result.terminal_reason == "KEYBOARD_TARGET_NOT_OPERABLE"
    assert result.findings[0].confirmation.method == "activation_probe"
    assert "Enter and Space do nothing" in result.findings[0].summary


def test_reachable_working_target_is_an_agent_failure_not_a_barrier(tmp_path: Path) -> None:
    page = PAGE.format(
        "<a href='/help'>Help</a><a href='/about'>About</a>"
        "<button onclick=\"document.getElementById('out').textContent='Next'\">Continue</button>"
        "<p id='out'></p>"
    )
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path).run([tab("Continue")])
    assert result.outcome == "inconclusive"
    assert result.failure_kind == "agent_failure"
    assert result.findings == []
    assert "Not a site barrier" in result.diagnosis
    assert "after 3 Tab presses" in result.diagnosis


def test_scripted_barrier_that_does_not_reproduce_is_not_reported(tmp_path: Path) -> None:
    page = PAGE.format("<a href='/help'>Help</a><button data-testid='target'>Book</button>")
    with serve_pages({"/": page}) as origin:
        result = executor_for(
            origin,
            tmp_path,
            barrier_check={"required_focus_test_id": "target", "max_keyboard_actions": 2},
        ).run([ProposedActionV1(action=ActionKind.ESCAPE)] * 2)
    assert result.outcome == "agent_error"
    assert result.terminal_reason == "BARRIER_NOT_CONFIRMED"
    assert result.failure_kind == "agent_failure"
    assert result.findings == []


def test_real_keyboard_trap_is_confirmed(tmp_path: Path) -> None:
    page = PAGE.format(
        "<a href='/a'>Start</a>"
        "<input id='trap' aria-label='Card number'>"
        "<a href='/b'>After the widget</a>"
        "<script>const trap = document.getElementById('trap');"
        "trap.addEventListener('keydown', (event) => {"
        " if (event.key === 'Tab' || event.key === 'Escape') { event.preventDefault(); trap.focus(); }"
        "});</script>"
    )
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path, no_progress_limit=3).run([tab()] * 8)
    assert result.outcome == "blocked"
    assert result.terminal_reason == "KEYBOARD_TRAP_CONFIRMED"
    [finding] = result.findings
    assert finding.rule_id == "no-keyboard-trap"
    assert finding.element.name == "Card number"


def test_small_page_that_wraps_around_is_not_a_trap(tmp_path: Path) -> None:
    page = PAGE.format("<a href='/a'>One</a><a href='/b'>Two</a>")
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path, no_progress_limit=3).run([tab()] * 12)
    assert result.outcome == "agent_error"
    assert result.terminal_reason == "REPEATED_FOCUS_CYCLE"
    assert result.failure_kind == "agent_failure"
    assert "Not a keyboard trap" in result.diagnosis
    results = {item.rule_id: item.result for item in result.rule_results}
    assert results["no-keyboard-trap"] == "passed"


class StoppingPlanner:
    stop_reason = "GROQ_QUOTA_FAILURE"
    stop_detail = "rate limited"

    def propose_next_action(self, observation: PlannerObservationV1):
        return None

    def record_outcome(self, *args) -> None:
        return None

    def runtime_metadata(self) -> dict[str, object]:
        return {}


def test_provider_failure_says_nothing_about_the_site(tmp_path: Path) -> None:
    page = PAGE.format("<div onclick='x()' style='cursor:pointer'>Pay now</div>")
    with serve_pages({"/": page}) as origin:
        result = executor_for(origin, tmp_path).run_with_planner(StoppingPlanner(), goal="Pay")
    assert result.outcome == "agent_error"
    assert result.failure_kind == "provider_failure"
    assert result.findings == []
    assert "says nothing about the website" in result.diagnosis


def test_collector_merges_repeats_and_applies_ignores() -> None:
    rule_set = resolve_rules(
        {
            "preset": "wcag22-aa",
            "ignores": [
                {"id": "name-role-value", "match": "toggle", "reason": "A11Y-12", "until": "2099-01-01"}
            ],
        }
    )
    collector = FindingCollector(rule_set)
    element = {"tag": "input", "css_path": "ul > li > input.toggle", "name": ""}
    for _ in range(3):
        collector.add(
            "name-role-value",
            summary="Checkbox has no name",
            url="https://todo.example/#/",
            method="dom_scan",
            element=element,
            merge_key="input.toggle",
        )
    collector.add("focus-appearance", summary="x", url="https://todo.example/", method="focus_diff")
    [finding] = collector.findings
    assert finding.occurrences == 3
    assert finding.ignored and finding.ignore_reason == "A11Y-12"
    results = {item.rule_id: item.result for item in collector.results()}
    assert results["name-role-value"] == "failed"
    assert results["focus-visible"] == "not_checked"
    assert "focus-appearance" not in results
