"""The accessibility report page, its exports, and the benchmark measures."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from django.urls import reverse

from apps.journeys.models import Journey
from apps.runs.benchmark import BenchmarkResult, summarize
from apps.runs.models import Finding, Run
from apps.runs.report import build_report


def _journey(**config) -> Journey:
    return Journey.objects.create(
        name="Report journey",
        goal="Book an appointment using only the keyboard.",
        start_url="https://clinic.example/",
        allowed_origins=["https://clinic.example"],
        completion_policy={},
        evaluation_config=config,
    )


def _run(journey: Journey, *, outcome: str, failure_kind: str = "", diagnosis: str = "") -> Run:
    started = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    return Run.objects.create(
        journey=journey,
        planner_provider="groq",
        planner_model="openai/gpt-oss-120b",
        status="succeeded" if outcome in {"completed", "blocked"} else "failed",
        outcome=outcome,
        failure_kind=failure_kind,
        diagnosis=diagnosis,
        started_at=started,
        finished_at=started + timedelta(seconds=75),
        planner_metadata={"rules": {"preset": "wcag22-aa", "catalog_version": "2026.10.29", "fail_on": "serious"}},
        rule_results=[
            {"rule_id": "keyboard-operable", "result": "failed", "detail": "", "finding_count": 1},
            {"rule_id": "focus-visible", "result": "passed", "detail": "", "finding_count": 0},
            {"rule_id": "bypass-blocks", "result": "not_applicable", "detail": "", "finding_count": 0},
        ],
    )


def _finding(run: Run, *, rule_id="keyboard-operable", severity="critical", status="confirmed", ignored=False):
    data = {
        "id": f"{rule_id}-{status}-{ignored}"[:16].ljust(16, "0"),
        "rule_id": rule_id,
        "wcag_criterion": "2.1.1",
        "wcag_level": "A",
        "severity": severity,
        "status": status,
        "summary": "“09:00” is skipped by Tab.",
        "element": {"name": "09:00", "css_path": "main > button.slot", "html_snippet": "<button class=\"slot\" tabindex=\"-1\">"},
        "confirmation": {"method": "tab_walk", "confirmed": True, "detail": ""},
        "occurrences": 3,
        "ignored": ignored,
        "ignore_reason": "A11Y-12" if ignored else "",
        "help_url": "https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html",
    }
    return Finding.objects.create(
        run=run, finding_id=data["id"], rule_id=rule_id, wcag_criterion="2.1.1", severity=severity,
        status=status, title="Every control works with the keyboard", summary=data["summary"],
        step_number=4, url="https://clinic.example/slots", ignored=ignored, data=data,
    )


@pytest.mark.django_db
def test_blocked_run_reads_as_blocked_in_plain_words() -> None:
    run = _run(_journey(), outcome="blocked", failure_kind="site_barrier")
    _finding(run)
    report = build_report(run)
    assert report["verdict"]["label"] == "Blocked"
    assert report["stats"]["confirmed"] == 1
    assert report["plain_words"].startswith("A keyboard user cannot finish “Report journey”.")
    assert "(WCAG 2.1.1, critical, step 4)" in report["plain_words"]
    assert report["stats"]["rules_passed"] == 1 and report["stats"]["rules_checked"] == 2
    assert report["duration"] == "1m 15s"


@pytest.mark.django_db
def test_completed_run_with_only_review_items_needs_review_and_ignores_do_not_fail() -> None:
    run = _run(_journey(), outcome="completed")
    _finding(run, status="needs_review", severity="serious")
    _finding(run, rule_id="focus-visible", ignored=True)
    report = build_report(run)
    assert report["verdict"]["key"] == "review"
    assert report["stats"]["ignored"] == 1
    assert "1 item needs a person to review" in report["plain_words"]


@pytest.mark.django_db
def test_agent_failure_is_incomplete_and_does_not_blame_the_site() -> None:
    run = _run(
        _journey(), outcome="agent_error", failure_kind="agent_failure",
        diagnosis="Not a site barrier: “Continue” is reachable after 3 Tab presses.",
    )
    report = build_report(run)
    assert report["verdict"]["label"] == "Incomplete"
    assert "the site was not blamed" in report["plain_words"]
    assert "Not a site barrier" in report["plain_words"]


@pytest.mark.django_db
def test_report_page_shows_tabs_findings_and_exports(client) -> None:
    run = _run(_journey(), outcome="blocked", failure_kind="site_barrier")
    _finding(run)
    content = client.get(reverse("runs:detail", kwargs={"run_id": run.id})).content.decode()
    assert 'role="tablist"' in content
    assert "Findings map" in content and "Fixes &amp; re-checks" in content
    assert "In plain words" in content
    assert "main &gt; button.slot" in content
    assert "Tab walk from the top of the page" in content
    assert reverse("runs:report_html", kwargs={"run_id": run.id}) in content


@pytest.mark.django_db
def test_json_export_is_plain_data(client) -> None:
    run = _run(_journey(), outcome="blocked", failure_kind="site_barrier")
    _finding(run)
    response = client.get(reverse("runs:report_json", kwargs={"run_id": run.id}))
    assert response["Content-Disposition"].startswith("attachment;")
    data = json.loads(response.content)
    assert data["schema_version"] == "accesspath_report.v1"
    assert data["verdict"]["key"] == "blocked"
    assert data["findings"][0]["element"]["css_path"] == "main > button.slot"
    assert {item["rule_id"] for item in data["rule_results"]} == {
        "keyboard-operable", "focus-visible", "bypass-blocks"
    }


@pytest.mark.django_db
def test_html_export_is_standalone(client) -> None:
    run = _run(_journey(), outcome="blocked", failure_kind="site_barrier")
    _finding(run)
    response = client.get(reverse("runs:report_html", kwargs={"run_id": run.id}))
    html = response.content.decode()
    assert response["Content-Disposition"].endswith('.html"')
    assert "<style>" in html and "fonts.googleapis" not in html
    assert 'id="accesspath-report"' in html
    assert "Every control works with the keyboard" in html


def _result(key, outcome, rules, expected_outcome="blocked", expected=("keyboard-operable",), reason=""):
    return BenchmarkResult(
        journey_key=key, run_id="r", expected_outcome=expected_outcome, expected_rules=list(expected),
        outcome=outcome, terminal_reason=reason, failure_kind="", confirmed_rules=list(rules),
        duration_seconds=10.0,
    )


def test_benchmark_summary_computes_the_gate_1_measures() -> None:
    results = [
        _result("a", "blocked", ["keyboard-operable"]),
        _result("a", "blocked", ["keyboard-operable"]),
        _result("b", "completed", [], "completed", ()),
        _result("b", "agent_error", ["focus-visible"], "completed", (), reason="GROQ_QUOTA_FAILURE"),
    ]
    summary = summarize(results)
    metrics = summary["metrics"]
    assert metrics["trustworthy_rate"] == 0.75
    assert metrics["barrier_precision"] == round(2 / 3, 3)
    assert metrics["known_barriers_found"] == 1.0
    assert metrics["repeatability"] == 0.5
    assert metrics["within_free_tier_rate"] == 0.75
    assert summary["gate_1"]["met"]["barrier_precision"] is False
    assert summary["gate_1"]["met"]["known_barriers_found"] is True


@pytest.mark.django_db
def test_run_benchmark_command_runs_a_journey_and_saves_the_summary(tmp_path, settings) -> None:
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path

    from django.core.management import call_command

    root = Path(settings.BASE_DIR) / "fixtures" / "clinic"

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings.FIXTURE_ALLOWED_ORIGINS = (f"http://127.0.0.1:{server.server_port}",)
        settings.MEDIA_ROOT = tmp_path
        call_command("seed_fixture_journeys")
        output = tmp_path / "summary.json"
        call_command(
            "run_benchmark", "--journeys", "bench-span-button", "--output", str(output)
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["metrics"]["runs"] == 1
    assert summary["results"][0]["outcome"] == "blocked"
    assert summary["results"][0]["matches"] is True
