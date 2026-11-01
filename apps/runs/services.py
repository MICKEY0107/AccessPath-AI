"""Application service coordinating durable runs and the generic engine."""

from __future__ import annotations

import os
from contextlib import contextmanager, nullcontext, suppress
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections, transaction

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
    # Playwright's sync API runs our step callback in its own greenlet context, where
    # Django would open a second database connection; reuse this one instead.
    main_connection = connections[DEFAULT_DB_ALIAS]

    def persist_steps() -> None:
        """Save buffered steps; whatever fails to save stays buffered for the next try."""
        batch = list(pending_steps)
        if not batch:
            return
        connections[DEFAULT_DB_ALIAS] = main_connection
        with sync_orm_allowed(), transaction.atomic():
            for evidence, artifacts in batch:
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
        del pending_steps[: len(batch)]

    def capture_step(evidence, artifacts: list[StoredArtifact]) -> None:
        """Save each step as it happens, so the run page shows progress live."""
        pending_steps.append((evidence, artifacts))
        # Saving progress must never stop the run; anything unsaved is retried at the end.
        with suppress(Exception):
            persist_steps()

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
    session_state, session_note = _saved_session(run)
    target_policy, staging_writes = _target_policy(run.journey)
    executor = KeyboardExecutor(
        run_id=run.id,
        start_url=run.journey.start_url,
        allowed_origins=run.journey.allowed_origins,
        target_policy=target_policy,
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
        session_state=session_state,
    )
    try:
        with _fixture_site(run.journey):
            result = executor.run_with_planner(planner, goal=run.journey.goal)
    finally:
        persist_steps()
        started_by = (run.planner_metadata or {}).get("started_by")
        run.planner_metadata = scrub(
            {
                **planner.runtime_metadata(),
                **credential_metadata,
                "started_by": started_by,
                "executor": executor.runtime_metadata,
                "rules": rule_set.to_metadata(),
                "probe_events": executor.probe_events,
                "session": session_note,
                # Pages seen while signed in are shown only to the person who started it.
                "signed_in": session_state is not None,
                "staging_writes": staging_writes,
                "writes_used": _writes_used(executor),
                "journey_key": run.journey.evaluation_config.get("journey_key", ""),
                "manifest_version": run.journey.evaluation_config.get("manifest_version", ""),
            },
            secrets,
        )
        run.save(update_fields=["planner_metadata"])
    _complete_run(run, result, secrets=secrets)
    try:
        from .code_mapping import map_run_findings

        # Code goes to an AI provider only when the repository's owner started the run.
        owner_started = started_by_repo_owner(run)
        map_run_findings(run, api_key=api_key if owner_started else "", use_ai=owner_started)
    except Exception as error:  # Mapping to code is extra; never lose the run's result.
        run.diagnosis = scrub(
            f"{run.diagnosis} Mapping findings to code failed ({type(error).__name__}).".strip(),
            secrets,
        )
        run.save(update_fields=["diagnosis"])
    return result


@contextmanager
def sync_orm_allowed():
    """Let the ORM run while Playwright's sync API holds an event loop in this thread.

    Playwright's sync API keeps an asyncio loop on the worker thread, so Django refuses
    database calls made between browser steps. Nothing else uses that loop while the
    executor's own (synchronous) code runs, so a blocking save here is safe; the worker
    runs one evaluation per process. The switch is an environment variable, so it is
    process-wide: keep Celery on its default prefork pool, not threads or gevent.
    """
    previous = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = previous


def _writes_used(executor) -> int:
    used = getattr(getattr(executor, "target_policy", None), "writes_used", 0)
    return used if isinstance(used, int) else 0


def _saved_session(run: Run) -> tuple[dict | None, str]:
    """The journey's saved sign-in, only for runs its owner started."""
    from apps.journeys.models import JourneySession
    from engine.session_state import limit_to_origins, parse_storage_state

    from .credentials import CredentialError, decrypt_session

    session = JourneySession.objects.filter(journey=run.journey).select_related("owner").first()
    if session is None:
        return None, ""
    if (run.planner_metadata or {}).get("started_by") != session.owner_id:
        return None, "A saved sign-in exists, but only runs its owner starts use it."
    staging = (run.journey.evaluation_config or {}).get("staging") or {}
    if staging.get("enabled") and staging.get("confirmed_by") != session.owner.get_username():
        # Someone else turned on form submissions: never submit them with this account.
        return None, "Not signed in: staging writes were turned on by someone else."
    try:
        state = parse_storage_state(decrypt_session(session.encrypted_state))
    except (CredentialError, ValueError):
        return None, "The saved sign-in could not be read; save it again."
    return limit_to_origins(state, run.journey.allowed_origins), f"Signed in ({session.summary})."


def _target_policy(journey) -> tuple[dict | None, int]:
    """The journey's request policy, with staging writes when its owner turned them on."""
    policy = journey.evaluation_config.get("target_policy")
    staging = journey.evaluation_config.get("staging") or {}
    if not (policy and journey.is_real_site and staging.get("enabled")):
        return policy, 0
    parsed = urlparse(journey.start_url)
    origin = f"{parsed.scheme}://{parsed.netloc}".lower()
    max_writes = max(1, min(20, int(staging.get("max_writes") or 5)))
    policy = {
        **policy,
        "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST"],
        "write_origins": [origin],
        "max_writes": max_writes,
    }
    return policy, max_writes


def _fixture_site(journey):
    """Serve the bundled fixture site for a fixture journey if nothing else does."""
    from engine.fixture_site import serve_if_missing

    if journey.execution_mode != "fixture":
        return nullcontext(False)
    parsed = urlparse(journey.start_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in {item.rstrip("/") for item in settings.FIXTURE_ALLOWED_ORIGINS}:
        return nullcontext(False)
    return serve_if_missing(origin, Path(settings.BASE_DIR) / "fixtures" / "clinic")


def started_by_repo_owner(run: Run) -> bool:
    """Whether the person who started ``run`` owns the journey's linked repository."""
    binding = run.journey.repo_binding
    started_by = (run.planner_metadata or {}).get("started_by")
    return binding is not None and started_by is not None and started_by == binding.owner_id


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
