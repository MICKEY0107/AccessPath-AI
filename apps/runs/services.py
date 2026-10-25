"""Application service coordinating durable runs and the generic engine."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from django.conf import settings
from django.db import transaction

from engine.artifacts import LocalArtifactStore, StoredArtifact
from engine.contracts import StepEvidenceV1
from engine.executor import EvaluationResult, KeyboardExecutor
from engine.gemini import GoogleGeminiActionClient
from engine.groq import GroqActionClient
from engine.openrouter import OpenRouterActionClient
from engine.planner import planner_from_config

from .models import JourneyOutcome, PlannerProvider, Run, RunArtifact, RunStatus, RunStep


def execute_configured_run(run: Run) -> EvaluationResult:
    """Execute one persisted journey and preserve every browser observation."""
    if run.status not in {RunStatus.QUEUED, RunStatus.STARTING}:
        raise ValueError("RUN_IS_NOT_READY")

    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    run.error_detail = ""
    run.save(update_fields=["status", "started_at", "error_detail"])
    artifact_store = LocalArtifactStore(settings.MEDIA_ROOT, run.id)

    pending_steps: list[tuple[StepEvidenceV1, list[StoredArtifact]]] = []

    def capture_step(evidence, artifacts: list[StoredArtifact]) -> None:
        """Buffer callback data; Playwright invokes callbacks inside its event loop."""
        pending_steps.append((evidence, artifacts))

    def persist_steps() -> None:
        with transaction.atomic():
            for evidence, artifacts in pending_steps:
                step = RunStep.objects.create(
                    run=run,
                    step_number=evidence.step_number,
                    evidence=evidence.model_dump(mode="json"),
                )
                RunArtifact.objects.bulk_create(
                    [
                        RunArtifact(
                            run=run,
                            step=step,
                            kind=artifact.kind,
                            relative_path=artifact.relative_path,
                            sha256=artifact.sha256,
                        )
                        for artifact in artifacts
                    ]
                )

    planner_config = deepcopy(run.journey.evaluation_config)
    configured_planner = planner_config.get("planner")
    if not isinstance(configured_planner, dict):
        raise ValueError("JOURNEY_PLANNER_CONFIGURATION_REQUIRED")
    fallback_config = configured_planner.get("fallback")
    if run.planner_provider == PlannerProvider.FIXTURE:
        if not isinstance(fallback_config, dict):
            raise ValueError("FIXTURE_FALLBACK_PLAN_REQUIRED")
        planner_config["planner"] = fallback_config
    elif run.planner_provider == PlannerProvider.OPENROUTER:
        configured_planner["kind"] = "openrouter.v1"
    elif run.planner_provider == PlannerProvider.GROQ:
        configured_planner["kind"] = "groq.v1"
    elif run.planner_provider != PlannerProvider.GEMINI:
        raise ValueError("UNSUPPORTED_PLANNER_PROVIDER")

    gemini_client = None
    if run.planner_provider == PlannerProvider.GEMINI and settings.GEMINI_API_KEY:
        gemini_client = GoogleGeminiActionClient.from_api_key(
            settings.GEMINI_API_KEY,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    openrouter_client = None
    if run.planner_provider == PlannerProvider.OPENROUTER and settings.OPENROUTER_API_KEY:
        openrouter_client = OpenRouterActionClient(
            api_key=settings.OPENROUTER_API_KEY,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    groq_client = None
    if run.planner_provider == PlannerProvider.GROQ and settings.GROQ_API_KEY:
        groq_client = GroqActionClient(
            api_key=settings.GROQ_API_KEY,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    planner = planner_from_config(
        planner_config,
        gemini_client=gemini_client,
        gemini_model=run.planner_model,
        openrouter_client=openrouter_client,
        openrouter_model=run.planner_model,
        groq_client=groq_client,
        groq_model=run.planner_model,
        max_calls=settings.PLANNER_MAX_CALLS_PER_RUN,
        max_quota_retries=settings.PLANNER_MAX_429_RETRIES,
        quota_backoff_seconds=settings.PLANNER_429_BACKOFF_SECONDS,
        max_transient_retries=settings.PLANNER_MAX_TRANSIENT_RETRIES,
        transient_backoff_seconds=settings.PLANNER_TRANSIENT_BACKOFF_SECONDS,
    )
    executor = KeyboardExecutor(
        run_id=run.id,
        start_url=run.journey.start_url,
        allowed_origins=run.journey.allowed_origins,
        target_policy=run.journey.evaluation_config.get("target_policy"),
        completion_policy=run.journey.completion_policy,
        barrier_check=run.journey.evaluation_config.get("barrier_check"),
        max_steps=settings.EVALUATOR_MAX_STEPS,
        action_timeout_ms=settings.EVALUATOR_ACTION_TIMEOUT_MS,
        headless=settings.EVALUATOR_HEADLESS,
        browser_executable_path=settings.EVALUATOR_BROWSER_EXECUTABLE,
        artifact_store=artifact_store,
        on_step=capture_step,
    )
    try:
        result = executor.run_with_planner(planner, goal=run.journey.goal)
    finally:
        persist_steps()
        run.planner_metadata = {
            **planner.runtime_metadata(),
            "executor": executor.runtime_metadata,
            "journey_key": run.journey.evaluation_config.get("journey_key", ""),
            "manifest_version": run.journey.evaluation_config.get("manifest_version", ""),
        }
        run.save(update_fields=["planner_metadata"])
    _complete_run(run, result)
    return result


def _complete_run(run: Run, result: EvaluationResult) -> None:
    outcome_map = {
        "completed": JourneyOutcome.COMPLETED,
        "blocked": JourneyOutcome.BLOCKED,
        "inconclusive": JourneyOutcome.INCONCLUSIVE,
        "agent_error": JourneyOutcome.AGENT_ERROR,
        "safety_stopped": JourneyOutcome.SAFETY_STOPPED,
        "environment_blocked": JourneyOutcome.ENVIRONMENT_BLOCKED,
    }
    run.outcome = outcome_map.get(result.outcome, JourneyOutcome.SYSTEM_ERROR)
    run.status = (
        RunStatus.SUCCEEDED
        if result.outcome in {"completed", "blocked", "inconclusive"}
        else RunStatus.FAILED
    )
    run.terminal_reason = result.terminal_reason
    run.error_detail = result.detail
    run.finished_at = datetime.now(UTC)
    run.save(
        update_fields=["outcome", "status", "terminal_reason", "error_detail", "finished_at"]
    )


def fail_run(run: Run, *, outcome: str, reason: str, detail: str) -> None:
    """Persist an expected environment/engine failure without hiding its cause."""
    run.status = RunStatus.FAILED
    run.outcome = outcome
    run.terminal_reason = reason[:128]
    run.error_detail = detail
    run.finished_at = datetime.now(UTC)
    run.save(update_fields=["status", "outcome", "terminal_reason", "error_detail", "finished_at"])
