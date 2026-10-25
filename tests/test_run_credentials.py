import json
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.journeys.models import Journey
from apps.runs.credentials import (
    CredentialError,
    mask_api_key,
    open_api_key,
    scrub,
    seal_api_key,
    validate_model,
)
from apps.runs.models import PlannerProvider, Run, RunStatus
from apps.runs.services import execute_configured_run
from apps.runs.tasks import execute_run
from engine.executor import EvaluationResult

USER_KEY = "gsk_user_supplied_secret_1234"


def _journey() -> Journey:
    return Journey.objects.create(
        name="Configured fixture",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={
            "planner": {"kind": "gemini.v1", "fallback": {"kind": "fixture_plan.v1"}}
        },
    )


def test_sealed_key_round_trips_and_is_not_plaintext() -> None:
    token = seal_api_key(USER_KEY)

    assert USER_KEY not in token
    assert open_api_key(token) == USER_KEY


def test_tampered_or_foreign_token_is_rejected() -> None:
    with pytest.raises(CredentialError):
        open_api_key("not-a-token")
    token = seal_api_key(USER_KEY)
    with override_settings(SECRET_KEY="another-secret"), pytest.raises(CredentialError):
        open_api_key(token)


def test_scrub_and_mask_hide_the_key() -> None:
    nested = {"detail": f"401 for key={USER_KEY}", "events": [USER_KEY, 3]}

    assert USER_KEY not in json.dumps(scrub(nested, [USER_KEY]))
    assert mask_api_key(USER_KEY) == "••••1234"
    assert validate_model("openai/gpt-4.1-mini") is None
    assert validate_model("bad model") is not None


@override_settings(GROQ_API_KEY="", GROQ_MODEL="")
def test_start_run_with_typed_key_and_model_seals_the_key_for_the_worker(client, db) -> None:
    journey = _journey()
    task = Mock(id="celery-task-1")

    with patch("apps.runs.views.execute_run.delay", return_value=task) as delay:
        response = client.post(
            reverse("runs:start", kwargs={"journey_id": journey.id}),
            {"planner_provider": "groq", "planner_model": "llama-3.3-70b", "api_key": USER_KEY},
        )

    run = Run.objects.get(journey=journey)
    assert response.status_code == 302
    assert run.planner_provider == "groq"
    assert run.planner_model == "llama-3.3-70b"
    assert run.planner_metadata == {"credential_source": "user_supplied"}
    token = delay.call_args.kwargs["credential_token"]
    assert open_api_key(token) == USER_KEY
    stored = json.dumps(list(Run.objects.values()), default=str)
    assert USER_KEY not in stored


@override_settings(GROQ_API_KEY="server-key", GROQ_MODEL="server-model")
def test_start_run_falls_back_to_server_key_and_model(client, db) -> None:
    journey = _journey()
    task = Mock(id="celery-task-1")

    with patch("apps.runs.views.execute_run.delay", return_value=task) as delay:
        client.post(
            reverse("runs:start", kwargs={"journey_id": journey.id}),
            {"planner_provider": "groq", "planner_model": "", "api_key": ""},
        )

    run = Run.objects.get(journey=journey)
    assert run.planner_model == "server-model"
    assert run.planner_metadata == {"credential_source": "environment"}
    delay.assert_called_once_with(str(run.id))


@override_settings(GROQ_API_KEY="", GROQ_MODEL="")
def test_start_run_requires_a_model_when_no_server_default_exists(client, db) -> None:
    journey = _journey()

    response = client.post(
        reverse("runs:start", kwargs={"journey_id": journey.id}),
        {"planner_provider": "groq", "api_key": USER_KEY},
        follow=True,
    )

    assert Run.objects.count() == 0
    assert "Enter the model to use for this run." in response.content.decode()


def test_start_run_rejects_an_invalid_model_id(client, db) -> None:
    journey = _journey()

    response = client.post(
        reverse("runs:start", kwargs={"journey_id": journey.id}),
        {"planner_provider": "groq", "planner_model": "drop table", "api_key": USER_KEY},
        follow=True,
    )

    assert Run.objects.count() == 0
    assert "without spaces" in response.content.decode()


@override_settings(GROQ_API_KEY="", GROQ_MODEL="")
def test_run_form_offers_key_and_model_fields_without_leaking_server_keys(client, db) -> None:
    _journey()

    with override_settings(OPENROUTER_API_KEY="server-openrouter-secret"):
        content = client.get(reverse("runs:list")).content.decode()

    assert 'name="api_key"' in content
    assert 'type="password"' in content
    assert 'name="planner_model"' in content
    assert "server-openrouter-secret" not in content


def _run_service_with_fake_executor(run: Run, *, user_api_key: str, detail: str = ""):
    fake_executor = Mock()
    fake_executor.runtime_metadata = {}
    fake_executor.run_with_planner.return_value = EvaluationResult(
        outcome="completed",
        terminal_reason="COMPLETION_POLICY_SATISFIED",
        steps_completed=0,
        detail=detail,
    )
    with (
        patch("apps.runs.services.GroqActionClient") as groq_client,
        patch("apps.runs.services.KeyboardExecutor", return_value=fake_executor),
    ):
        execute_configured_run(run, user_api_key=user_api_key)
    return groq_client


@override_settings(GROQ_API_KEY="server-key")
def test_service_uses_the_typed_key_and_scrubs_it_from_saved_detail(db) -> None:
    run = Run.objects.create(
        journey=_journey(), planner_provider=PlannerProvider.GROQ, planner_model="m"
    )

    groq_client = _run_service_with_fake_executor(
        run, user_api_key=USER_KEY, detail=f"provider echoed {USER_KEY}"
    )

    assert groq_client.call_args.kwargs["api_key"] == USER_KEY
    run.refresh_from_db()
    assert USER_KEY not in run.error_detail
    assert "[redacted]" in run.error_detail
    assert run.planner_metadata["credential_source"] == "user_supplied"
    assert run.planner_metadata["credential_hint"] == "••••1234"
    assert USER_KEY not in json.dumps(run.planner_metadata)


@override_settings(GROQ_API_KEY="server-key")
def test_service_falls_back_to_the_environment_key(db) -> None:
    run = Run.objects.create(
        journey=_journey(), planner_provider=PlannerProvider.GROQ, planner_model="m"
    )

    groq_client = _run_service_with_fake_executor(run, user_api_key="")

    assert groq_client.call_args.kwargs["api_key"] == "server-key"
    run.refresh_from_db()
    assert run.planner_metadata["credential_source"] == "environment"


def test_worker_fails_safely_when_the_sealed_key_cannot_be_opened(db) -> None:
    run = Run.objects.create(journey=_journey(), planner_provider=PlannerProvider.GROQ)

    result = execute_run.apply(args=[str(run.id)], kwargs={"credential_token": "bogus"}).get()

    run.refresh_from_db()
    assert result["outcome"] == "environment_blocked"
    assert run.status == RunStatus.FAILED
    assert run.terminal_reason == "RUN_CREDENTIAL_UNAVAILABLE"


def test_worker_never_reraises_an_error_that_contains_the_key(db) -> None:
    run = Run.objects.create(journey=_journey(), planner_provider=PlannerProvider.GROQ)
    token = seal_api_key(USER_KEY)

    with (
        patch(
            "apps.runs.tasks.execute_configured_run",
            side_effect=RuntimeError(f"bad key {USER_KEY}"),
        ),
        pytest.raises(RuntimeError) as raised,
    ):
        execute_run.apply(args=[str(run.id)], kwargs={"credential_token": token}).get()

    run.refresh_from_db()
    assert USER_KEY not in str(raised.value)
    assert USER_KEY not in run.error_detail


def test_run_detail_shows_the_model_and_only_a_masked_key(client, db) -> None:
    run = Run.objects.create(
        journey=_journey(),
        planner_provider=PlannerProvider.GROQ,
        planner_model="llama-3.1-8b-instant",
        planner_metadata={
            "provider_label": "Groq",
            "model": "llama-3.1-8b-instant",
            "calls": 2,
            "credential_source": "user_supplied",
            "credential_hint": "••••1234",
        },
    )

    content = client.get(reverse("runs:detail", kwargs={"run_id": run.id})).content.decode()

    assert "llama-3.1-8b-instant" in content
    assert "Your API key (••••1234)" in content
