"""Worker tasks. Browser execution is introduced behind this module in Phase 1C."""

from __future__ import annotations

from celery import shared_task

from .credentials import CredentialError, open_api_key, scrub
from .models import Run, RunStatus
from .services import execute_configured_run, fail_run


@shared_task(name="accesspath.health_check")
def health_check() -> dict[str, str]:
    """Small Phase 1A task proving broker-to-worker connectivity."""
    return {"status": "ok"}


@shared_task(bind=True, name="accesspath.execute_run")
def execute_run(self, run_id: str, credential_token: str = "") -> dict[str, str | int]:
    """Execute a configured journey away from the web-request process.

    ``credential_token`` is a sealed, short-lived API key typed into the run form;
    without it the worker falls back to the provider key from the environment.
    """
    run = Run.objects.select_related("journey").get(pk=run_id)
    if run.status != RunStatus.QUEUED:
        return {"status": run.status, "outcome": run.outcome}

    user_api_key = ""
    if credential_token:
        try:
            user_api_key = open_api_key(credential_token)
        except CredentialError as error:
            fail_run(
                run,
                outcome="environment_blocked",
                reason="RUN_CREDENTIAL_UNAVAILABLE",
                detail=f"{error}: start the run again and re-enter the API key.",
            )
            return {"status": "failed", "outcome": "environment_blocked"}

    run.status = RunStatus.STARTING
    run.celery_task_id = self.request.id or ""
    run.save(update_fields=["status", "celery_task_id"])
    try:
        result = execute_configured_run(run, user_api_key=user_api_key)
        return {
            "status": Run.objects.get(pk=run_id).status,
            "outcome": result.outcome,
            "steps": result.steps_completed,
        }
    except ValueError as error:
        fail_run(
            run,
            outcome="safety_stopped",
            reason="CONFIGURATION_OR_SAFETY_STOP",
            detail=str(error),
            secrets=[user_api_key],
        )
        return {"status": "failed", "outcome": "safety_stopped"}
    except Exception as error:
        fail_run(
            run,
            outcome="system_error",
            reason="EXECUTOR_EXCEPTION",
            detail=f"{type(error).__name__}: {error}",
            secrets=[user_api_key],
        )
        if user_api_key and user_api_key in str(error):
            # Celery logs and stores the raised error; never let it carry the key.
            raise RuntimeError(scrub(f"{type(error).__name__}: {error}", [user_api_key])) from None
        raise
