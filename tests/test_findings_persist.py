"""Findings, rule results, and the diagnosis are saved with the run."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from apps.journeys.models import Journey
from apps.runs.models import Finding, PlannerProvider, Run
from apps.runs.services import execute_configured_run
from engine.contracts import FindingConfirmationV1, FindingV1, RuleResultV1
from engine.executor import EvaluationResult

SECRET = "gsk_secret_value_9999"


@pytest.mark.django_db
def test_service_saves_findings_rule_results_and_diagnosis() -> None:
    journey = Journey.objects.create(
        name="Persist journey",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={"planner": {"kind": "gemini.v1", "fallback": {"kind": "fixture_plan.v1"}}},
        rule_config={"preset": "essential"},
    )
    run = Run.objects.create(journey=journey, planner_provider=PlannerProvider.GROQ, planner_model="m")
    finding = FindingV1(
        id="abc123def4567890",
        rule_id="keyboard-operable",
        wcag_criterion="2.1.1",
        wcag_level="A",
        severity="critical",
        status="confirmed",
        title="Every control works with the keyboard",
        summary=f"Pay now is skipped by Tab ({SECRET})",
        step_number=3,
        url="http://127.0.0.1:8001/pay",
        confirmation=FindingConfirmationV1(method="tab_walk", confirmed=True),
    )
    fake_executor = Mock()
    fake_executor.runtime_metadata = {}
    fake_executor.probe_events = []
    fake_executor.run_with_planner.return_value = EvaluationResult(
        outcome="blocked",
        terminal_reason="KEYBOARD_TARGET_NOT_REACHABLE",
        steps_completed=3,
        failure_kind="site_barrier",
        diagnosis="",
        findings=[finding],
        rule_results=[RuleResultV1(rule_id="keyboard-operable", result="failed", finding_count=1)],
    )
    with (
        patch("apps.runs.services.GroqActionClient"),
        patch("apps.runs.services.KeyboardExecutor", return_value=fake_executor) as executor_class,
    ):
        execute_configured_run(run, user_api_key=SECRET)

    rule_set = executor_class.call_args.kwargs["rule_set"]
    assert rule_set.preset == "essential"
    run.refresh_from_db()
    assert run.outcome == "blocked"
    assert run.failure_kind == "site_barrier"
    assert run.rule_results == [
        {"rule_id": "keyboard-operable", "result": "failed", "detail": "", "finding_count": 1}
    ]
    assert run.planner_metadata["rules"]["preset"] == "essential"
    saved = Finding.objects.get(run=run)
    assert saved.rule_id == "keyboard-operable"
    assert saved.severity == "critical"
    assert SECRET not in saved.summary
    assert SECRET not in str(saved.data)
