"""Application service coordinating durable runs and the generic engine."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction

from apps.journeys.real_sites import host_is_public
from engine.artifacts import LocalArtifactStore, StoredArtifact
from engine.contracts import StepEvidenceV1
from engine.executor import EvaluationResult, KeyboardExecutor
from engine.gemini import GoogleGeminiActionClient
from engine.groq import GroqActionClient
from engine.ollama import OllamaActionClient
from engine.openrouter import OpenRouterActionClient
from engine.planner import planner_from_config
from engine.rules import resolve_rules

from .credentials import mask_api_key, scrub
from .models import (
    Finding,
    JourneyOutcome,
    PlannerProvider,
    Run,
    RunArtifact,
    RunStatus,
    RunStep,
)


def _environment_api_key(provider: str) -> str:
    return {
        PlannerProvider.GEMINI: settings.GEMINI_API_KEY,
        PlannerProvider.OPENROUTER: settings.OPENROUTER_API_KEY,
        PlannerProvider.GROQ: settings.GROQ_API_KEY,
    }.get(provider, "")


def execute_configured_run(run: Run, *, user_api_key: str = "") -> EvaluationResult:
    """Execute one persisted journey and preserve every browser observation.

    ``user_api_key`` is a key the person typed for this run; when it is empty the
    provider's environment key is used. Either way the key stays in memory and is
    scrubbed from evidence, metadata, and error detail before they are saved.
    """
    if run.status not in {RunStatus.QUEUED, RunStatus.STARTING}:
        raise ValueError("RUN_IS_NOT_READY")

    if run.journey.is_real_site and not settings.ALLOW_PRIVATE_NETWORKS:
        # Re-check at run time: a public name can be re-pointed at a private address.
        host = urlparse(run.journey.start_url).hostname or ""
        if not host_is_public(host):
            raise ValueError(f"REAL_SITE_HOST_NOT_PUBLIC:{host}")

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
                    evidence=scrub(evidence.model_dump(mode="json"), secrets),
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
    elif run.planner_provider == PlannerProvider.OLLAMA:
        configured_planner["kind"] = "ollama.v1"
    elif run.planner_provider != PlannerProvider.GEMINI:
        raise ValueError("UNSUPPORTED_PLANNER_PROVIDER")

    api_key = user_api_key or _environment_api_key(run.planner_provider)
    secrets = [api_key]
    credential_metadata: dict[str, str] = {}
    if run.planner_provider == PlannerProvider.OLLAMA:
        credential_metadata = {"credential_source": "none", "credential_hint": ""}
    elif run.planner_provider != PlannerProvider.FIXTURE:
        requested = (run.planner_metadata or {}).get("credential_source")
        credential_metadata = {
            "credential_source": (
                ("saved" if requested == "saved" else "user_supplied")
                if user_api_key
                else "environment"
            ),
            "credential_hint": mask_api_key(api_key) if api_key else "",
        }

    gemini_client = None
    if run.planner_provider == PlannerProvider.GEMINI and api_key:
        gemini_client = GoogleGeminiActionClient.from_api_key(
            api_key,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    openrouter_client = None
    if run.planner_provider == PlannerProvider.OPENROUTER and api_key:
        openrouter_client = OpenRouterActionClient(
            api_key=api_key,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    groq_client = None
    if run.planner_provider == PlannerProvider.GROQ and api_key:
        groq_client = GroqActionClient(
            api_key=api_key,
            timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
            min_interval_seconds=settings.PLANNER_MIN_CALL_INTERVAL_SECONDS,
        )
    ollama_client = None
    if run.planner_provider == PlannerProvider.OLLAMA and settings.OLLAMA_BASE_URL:
        ollama_client = OllamaActionClient(
            base_url=settings.OLLAMA_BASE_URL,
            timeout_seconds=max(settings.PLANNER_CALL_TIMEOUT_SECONDS, 120),
        )
    planner = planner_from_config(
        planner_config,
        gemini_client=gemini_client,
        gemini_model=run.planner_model,
        openrouter_client=openrouter_client,
        openrouter_model=run.planner_model,
        groq_client=groq_client,
        groq_model=run.planner_model,
        ollama_client=ollama_client,
        ollama_model=run.planner_model,
        max_calls=settings.PLANNER_MAX_CALLS_PER_RUN,
        max_quota_retries=settings.PLANNER_MAX_429_RETRIES,
        quota_backoff_seconds=settings.PLANNER_429_BACKOFF_SECONDS,
        max_transient_retries=settings.PLANNER_MAX_TRANSIENT_RETRIES,
        transient_backoff_seconds=settings.PLANNER_TRANSIENT_BACKOFF_SECONDS,
        max_invalid_retries=settings.PLANNER_MAX_INVALID_RETRIES,
    )
    try:
        rule_set = resolve_rules(run.journey.rule_config)
    except (ValueError, KeyError):
        # Settings saved against an older catalog fall back to the default preset.
        rule_set = resolve_rules({})
    axe_source = _axe_source()
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
        rule_set=rule_set,
        axe_source=axe_source,
        run_checks=settings.EVALUATOR_RUN_CHECKS,
    )
    try:
        result = executor.run_with_planner(planner, goal=run.journey.goal)
    finally:
        persist_steps()
        run.planner_metadata = scrub(
            {
                **planner.runtime_metadata(),
                **credential_metadata,
                "executor": executor.runtime_metadata,
                "rules": rule_set.to_metadata(),
                "probe_events": executor.probe_events,
                "journey_key": run.journey.evaluation_config.get("journey_key", ""),
                "manifest_version": run.journey.evaluation_config.get("manifest_version", ""),
            },
            secrets,
        )
        run.save(update_fields=["planner_metadata"])
    _complete_run(run, result, secrets=secrets)
    try:
        from .code_mapping import map_run_findings

        map_run_findings(run, api_key=api_key)
    except Exception as error:  # Mapping to code is extra; never lose the run's result.
        run.diagnosis = scrub(
            f"{run.diagnosis} Mapping findings to code failed ({type(error).__name__}).".strip(),
            secrets,
        )
        run.save(update_fields=["diagnosis"])
    return result


def _axe_source() -> str | None:
    path = settings.AXE_CORE_PATH
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else None
    except OSError:
        return None


def _save_findings(run: Run, result: EvaluationResult, *, secrets: list[str]) -> None:
    with transaction.atomic():
        Finding.objects.bulk_create(
            [
                Finding(
                    run=run,
                    finding_id=finding.id,
                    rule_id=finding.rule_id,
                    wcag_criterion=finding.wcag_criterion,
                    severity=finding.severity,
                    status=finding.status,
                    source=finding.source,
                    title=finding.title,
                    summary=scrub(finding.summary, secrets),
                    step_number=finding.step_number,
                    url=finding.url,
                    ignored=finding.ignored,
                    data=scrub(finding.model_dump(mode="json"), secrets),
                )
                for finding in result.findings
            ],
            ignore_conflicts=True,
        )


def _complete_run(run: Run, result: EvaluationResult, *, secrets: list[str]) -> None:
    _save_findings(run, result, secrets=secrets)
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
    run.error_detail = scrub(result.detail, secrets)
    run.failure_kind = result.failure_kind
    run.diagnosis = scrub(result.diagnosis, secrets)
    run.rule_results = [item.model_dump(mode="json") for item in result.rule_results]
    run.finished_at = datetime.now(UTC)
    run.save(
        update_fields=[
            "outcome",
            "status",
            "terminal_reason",
            "error_detail",
            "failure_kind",
            "diagnosis",
            "rule_results",
            "finished_at",
        ]
    )


def fail_run(
    run: Run, *, outcome: str, reason: str, detail: str, secrets: list[str] | None = None
) -> None:
    """Persist an expected environment/engine failure without hiding its cause."""
    run.status = RunStatus.FAILED
    run.outcome = outcome
    run.terminal_reason = reason[:128]
    run.error_detail = scrub(detail, secrets or [])
    run.finished_at = datetime.now(UTC)
    run.save(update_fields=["status", "outcome", "terminal_reason", "error_detail", "finished_at"])
