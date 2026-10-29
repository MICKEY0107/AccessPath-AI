"""Focus and page checks that run during an evaluation."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from page_server import executor_for, serve_pages
from test_browser_fixture_flow import _load_manifest, _serve_fixture

from engine.artifacts import LocalArtifactStore
from engine.contracts import ActionKind, ProposedActionV1
from engine.executor import KeyboardExecutor
from engine.planner import FixturePlanPlanner
from engine.rules import resolve_rules

PAGE = "<!doctype html><html lang='en'><head><title>t</title>{head}</head><body>{body}</body></html>"


def page(body: str, head: str = "") -> str:
    return PAGE.format(head=head, body=body)


def tab() -> ProposedActionV1:
    return ProposedActionV1(action=ActionKind.TAB)


def by_rule(result, rule_id: str):
    return [finding for finding in result.findings if finding.rule_id == rule_id]


def rule_result(result, rule_id: str) -> str:
    return {item.rule_id: item.result for item in result.rule_results}[rule_id]


def test_removed_focus_outline_is_reported(tmp_path: Path) -> None:
    html = page("<button>Save</button>", "<style>button:focus{outline:none}</style>")
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([tab()])
    [finding] = by_rule(result, "focus-visible")
    assert finding.status == "confirmed"
    assert finding.wcag_criterion == "2.4.7"
    assert finding.element.name == "Save"
    assert "looks exactly the same" in finding.summary


def test_default_focus_outline_passes(tmp_path: Path) -> None:
    with serve_pages({"/": page("<button>Save</button>")}) as origin:
        result = executor_for(origin, tmp_path).run([tab()])
    assert by_rule(result, "focus-visible") == []
    assert rule_result(result, "focus-visible") == "passed"


def test_focus_hidden_under_a_fixed_header_is_reported(tmp_path: Path) -> None:
    html = page(
        "<header><a href='/home'>Home</a></header><div><a href='/x'>Hidden link</a></div>",
        "<style>header{position:fixed;top:0;left:0;right:0;height:240px;"
        "background:#fff;z-index:10}</style>",
    )
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([tab(), tab()])
    [finding] = by_rule(result, "focus-not-obscured")
    assert finding.status == "confirmed"
    assert finding.element.name == "Hidden link"
    assert "completely hidden" in finding.summary


def test_unnamed_controls_are_grouped_and_confirmed_by_chromium(tmp_path: Path) -> None:
    html = page(
        "<ul><li><input class='toggle' type='checkbox'><label>Buy milk</label></li>"
        "<li><input class='toggle' type='checkbox'><label>Call the clinic</label></li></ul>"
        "<button class='destroy'></button>"
        "<button class='icon'><svg><title>Close</title></svg></button>"
    )
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([])
    findings = by_rule(result, "name-role-value")
    checkbox = next(item for item in findings if item.element.role == "checkbox")
    assert checkbox.occurrences == 2
    assert checkbox.status == "confirmed"
    assert any(item.element.classes == ["destroy"] for item in findings)
    # The SVG title gives the second button a name, so it is not reported.
    assert not any(item.element.classes == ["icon"] for item in findings)


def test_repeated_navigation_without_a_bypass_is_reported(tmp_path: Path) -> None:
    nav = "".join(f"<a href='/{index}'>Section {index}</a>" for index in range(5))
    html = page(f"<nav>{nav}</nav><div><button>Content action</button></div>")
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([])
    [finding] = by_rule(result, "bypass-blocks")
    assert finding.wcag_criterion == "2.4.1"
    assert "no skip link" in finding.summary


def test_working_skip_link_passes_bypass_blocks(tmp_path: Path) -> None:
    nav = "".join(f"<a href='/{index}'>Section {index}</a>" for index in range(5))
    html = page(
        f"<a href='#content'>Skip to content</a><nav>{nav}</nav>"
        "<div id='content'><button>Content action</button></div>"
    )
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([])
    assert by_rule(result, "bypass-blocks") == []
    assert rule_result(result, "bypass-blocks") == "passed"


def test_positive_tabindex_needs_review(tmp_path: Path) -> None:
    html = page("<a href='/a'>One</a><a href='/b' tabindex='3'>Two</a><a href='/c'>Three</a>")
    with serve_pages({"/": html}) as origin:
        result = executor_for(origin, tmp_path).run([])
    [finding] = by_rule(result, "focus-order")
    assert finding.status == "needs_review"
    assert rule_result(result, "focus-order") == "needs_review"


def test_focus_that_changes_the_page_is_reported(tmp_path: Path) -> None:
    html = page("<a href='/a'>One</a><a href='/b' onfocus=\"location.href='/other'\">Two</a>")
    with serve_pages({"/": html, "/other": page("<p>Other page</p>")}) as origin:
        result = executor_for(origin, tmp_path).run([])
    [finding] = by_rule(result, "on-focus")
    assert finding.status == "confirmed"
    assert "/other" in finding.summary


FAKE_AXE = """
window.axe = {
  version: 'test-1',
  run: async () => ({violations: [{
    id: 'color-contrast', impact: 'serious', tags: ['wcag2aa', 'wcag143'],
    help: 'Elements must meet minimum color contrast ratio thresholds',
    helpUrl: 'https://dequeuniversity.com/rules/axe/4.10/color-contrast',
    description: 'Ensure contrast between foreground and background colors is enough.',
    nodes: [{target: ['p.low'], html: '<p class="low">', failureSummary: 'Increase contrast'}]
  }]})
};
"""


def test_axe_violations_become_findings_with_their_wcag_criterion(tmp_path: Path) -> None:
    with serve_pages({"/": page("<p class='low'>Faint</p>")}) as origin:
        executor = KeyboardExecutor(
            **_kwargs(origin, tmp_path), rule_set=resolve_rules({}), axe_source=FAKE_AXE
        )
        result = executor.run([])
    [finding] = [item for item in result.findings if item.source == "axe"]
    assert finding.rule_id == "axe/color-contrast"
    assert finding.wcag_criterion == "1.4.3"
    assert finding.wcag_level == "AA"
    assert finding.severity == "serious"
    assert executor.runtime_metadata["axe"]["status"] == "ran"


def test_axe_is_reported_as_not_installed_or_not_in_preset(tmp_path: Path) -> None:
    with serve_pages({"/": page("<p>Hi</p>")}) as origin:
        missing = KeyboardExecutor(**_kwargs(origin, tmp_path))
        missing.run([])
        essential = KeyboardExecutor(
            **_kwargs(origin, tmp_path),
            rule_set=resolve_rules({"preset": "essential"}),
            axe_source=FAKE_AXE,
        )
        essential.run([])
    assert missing.runtime_metadata["axe"]["status"] == "not_installed"
    assert essential.runtime_metadata["axe"]["status"] == "not_in_preset"


def test_accessible_clinic_journey_has_no_findings(tmp_path: Path) -> None:
    server, thread, origin = _serve_fixture()
    try:
        journey = _load_manifest()["journeys"][0]
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}{journey['start_path']}",
            allowed_origins=[origin],
            completion_policy=journey["completion_policy"],
            barrier_check=None,
            max_steps=24,
            action_timeout_ms=5000,
            headless=True,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run(FixturePlanPlanner(journey["evaluation_config"]["planner"]["fallback"]).actions())
    finally:
        server.shutdown()
        thread.join(timeout=2)
    assert result.outcome == "completed"
    assert result.findings == []
    results = {item.rule_id: item.result for item in result.rule_results}
    assert results["focus-visible"] == "passed"
    assert results["name-role-value"] == "passed"
    assert "failed" not in results.values()


def _kwargs(origin: str, tmp_path: Path) -> dict:
    run_id = uuid4()
    return {
        "run_id": run_id,
        "start_url": f"{origin}/",
        "allowed_origins": [origin],
        "completion_policy": {"signals": [{"id": "n", "type": "url_path_equals", "expected": "/n"}]},
        "barrier_check": None,
        "max_steps": 4,
        "action_timeout_ms": 5000,
        "headless": True,
        "artifact_store": LocalArtifactStore(tmp_path, run_id),
        "on_step": lambda step, artifacts: None,
    }
