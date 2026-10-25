"""Opt-in proof against the reviewed public target; never part of the hermetic suite."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

from engine.artifacts import LocalArtifactStore
from engine.executor import KeyboardExecutor
from engine.gemini import GoogleGeminiActionClient
from engine.groq import GroqActionClient
from engine.openrouter import OpenRouterActionClient
from engine.planner import FixturePlanPlanner, planner_from_config

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_APPROVED_LIVE_TESTS", "").lower() != "true",
    reason="approved live-site tests require RUN_APPROVED_LIVE_TESTS=true",
)


def _wikipedia_journey() -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "public" / "journey-manifest.json"
    journeys = json.loads(path.read_text(encoding="utf-8"))["journeys"]
    return next(item for item in journeys if item["key"] == "wikipedia-web-accessibility-search")


def _w3c_smoke_journey() -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "public" / "journey-manifest.json"
    journeys = json.loads(path.read_text(encoding="utf-8"))["journeys"]
    return next(item for item in journeys if item["key"] == "w3c-bad-accessible-keyboard-smoke")


def test_w3c_accessible_page_keyboard_smoke(tmp_path: Path) -> None:
    journey = _w3c_smoke_journey()
    run_id = uuid4()
    evidence = []

    result = KeyboardExecutor(
        run_id=run_id,
        start_url=journey["start_url"],
        allowed_origins=journey["target_policy"]["navigation_origins"],
        target_policy=journey["target_policy"],
        completion_policy=journey["completion_policy"],
        barrier_check=None,
        max_steps=journey["target_policy"]["max_actions"],
        action_timeout_ms=5000,
        headless=True,
        browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=lambda step, artifacts: evidence.append((step, artifacts)),
    ).run(
        FixturePlanPlanner(
            journey["evaluation_config"]["planner"]["fallback"]
        ).actions()
    )

    assert (result.outcome, result.terminal_reason) == (
        "completed",
        "COMPLETION_POLICY_SATISFIED",
    ), evidence[-1][0].model_dump(mode="json") if evidence else result
    assert evidence[-1][0].focus_after is not None


@pytest.mark.parametrize("attempt", range(1, 6))
def test_wikipedia_read_only_keyboard_journey_completes(
    tmp_path: Path, attempt: int
) -> None:
    del attempt
    journey = _wikipedia_journey()
    fallback = journey["evaluation_config"]["planner"]["fallback"]
    run_id = uuid4()
    evidence = []

    result = KeyboardExecutor(
        run_id=run_id,
        start_url=journey["start_url"],
        allowed_origins=journey["target_policy"]["navigation_origins"],
        target_policy=journey["target_policy"],
        completion_policy=journey["completion_policy"],
        barrier_check=None,
        max_steps=journey["target_policy"]["max_actions"],
        action_timeout_ms=5000,
        headless=True,
        browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=lambda step, artifacts: evidence.append((step, artifacts)),
    ).run(FixturePlanPlanner(fallback).actions())

    trace = [
        {
            "step": step.step_number,
            "action": step.proposed_action.action.value,
            "before": step.focus_before.name if step.focus_before else None,
            "after": step.focus_after.name if step.focus_after else None,
            "role": step.focus_after.role if step.focus_after else None,
            "editable": step.focus_after.editable if step.focus_after else None,
            "tag": step.focus_after.tag if step.focus_after else None,
            "status": step.action_result.status,
            "url": str(step.url_after),
        }
        for step, _ in evidence
    ]
    assert (result.outcome, result.terminal_reason, result.detail) == (
        "completed",
        "COMPLETION_POLICY_SATISFIED",
        "",
    ), json.dumps(trace)
    assert result.steps_completed <= journey["target_policy"]["max_actions"]
    assert evidence[-1][0].url_after.path == "/wiki/Web_accessibility"
    assert evidence[-1][0].completion_signals == {
        "article_url": True,
        "article_heading": True,
    }
    assert all(step.policy_decision.outcome == "approved" for step, _ in evidence)


@pytest.mark.parametrize("attempt", range(1, 4))
def test_wikipedia_live_planner_completes_without_fallback(
    tmp_path: Path, attempt: int
) -> None:
    del attempt
    journey = _wikipedia_journey()
    provider = os.environ.get("LIVE_PLANNER_PROVIDER", "gemini").lower()
    if provider not in {"gemini", "openrouter", "groq"}:
        pytest.fail(f"Unsupported LIVE_PLANNER_PROVIDER: {provider}")
    key_name = f"{provider.upper()}_API_KEY"
    model_name = f"{provider.upper()}_MODEL"
    if not (os.environ.get(key_name) and os.environ.get(model_name)):
        pytest.skip(f"live planner proof requires {key_name} and {model_name}")

    timeout_seconds = float(os.environ.get("PLANNER_CALL_TIMEOUT_SECONDS", "30"))
    interval_seconds = float(os.environ.get("PLANNER_MIN_CALL_INTERVAL_SECONDS", "15"))
    planner_config = deepcopy(journey["evaluation_config"])
    planner_config["planner"]["kind"] = f"{provider}.v1"
    planner_clients = {
        "gemini_client": None,
        "openrouter_client": None,
        "groq_client": None,
    }
    if provider == "gemini":
        planner_clients["gemini_client"] = GoogleGeminiActionClient.from_api_key(
            os.environ[key_name],
            timeout_seconds=timeout_seconds,
            min_interval_seconds=interval_seconds,
        )
    elif provider == "openrouter":
        planner_clients["openrouter_client"] = OpenRouterActionClient(
            api_key=os.environ[key_name],
            timeout_seconds=timeout_seconds,
            min_interval_seconds=interval_seconds,
        )
    else:
        planner_clients["groq_client"] = GroqActionClient(
            api_key=os.environ[key_name],
            timeout_seconds=timeout_seconds,
            min_interval_seconds=interval_seconds,
        )
    planner = planner_from_config(
        planner_config,
        **planner_clients,
        gemini_model=os.environ.get("GEMINI_MODEL", ""),
        openrouter_model=os.environ.get("OPENROUTER_MODEL", ""),
        groq_model=os.environ.get("GROQ_MODEL", ""),
        max_calls=20,
        max_quota_retries=1,
        quota_backoff_seconds=5,
        max_transient_retries=2,
        transient_backoff_seconds=5,
    )
    run_id = uuid4()
    evidence = []

    result = KeyboardExecutor(
        run_id=run_id,
        start_url=journey["start_url"],
        allowed_origins=journey["target_policy"]["navigation_origins"],
        target_policy=journey["target_policy"],
        completion_policy=journey["completion_policy"],
        barrier_check=None,
        max_steps=journey["target_policy"]["max_actions"],
        action_timeout_ms=5000,
        headless=True,
        browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=lambda step, artifacts: evidence.append((step, artifacts)),
    ).run_with_planner(planner, goal=journey["goal"])

    trace = [
        (
            step.step_number,
            step.proposed_action.action.value,
            step.focus_after.name if step.focus_after else None,
            step.action_result.status,
            str(step.url_after),
        )
        for step, _ in evidence
    ]
    metadata = planner.runtime_metadata()
    assert (result.outcome, result.terminal_reason, result.detail) == (
        "completed",
        "COMPLETION_POLICY_SATISFIED",
        "",
    ), json.dumps(trace)
    assert metadata["provider"] == provider
    assert metadata["fallback_used"] is False, metadata
    assert metadata["calls"] >= 1
