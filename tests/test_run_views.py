from unittest.mock import Mock, patch

from django.test import override_settings
from django.urls import reverse

from apps.journeys.models import Journey
from apps.runs.models import JourneyOutcome, PlannerProvider, Run, RunArtifact, RunStatus, RunStep


def test_start_run_creates_durable_run_and_queues_worker(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured fixture",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={
            "schema_version": "completion_policy.v1",
            "signals": [
                {"id": "url", "type": "url_path_equals", "expected": "/confirmation"}
            ],
        },
        evaluation_config={"planner": {"kind": "fixture_plan.v1", "actions": []}},
    )
    task = Mock(id="celery-task-1")

    with patch("apps.runs.views.execute_run.delay", return_value=task) as delay:
        response = client.post(reverse("runs:start", kwargs={"journey_id": journey.id}))

    run = Run.objects.get(journey=journey)
    assert response.status_code == 302
    assert response.url == reverse("runs:detail", kwargs={"run_id": run.id})
    assert run.celery_task_id == "celery-task-1"
    delay.assert_called_once_with(str(run.id))


@override_settings(
    GEMINI_API_KEY="gemini-key",
    GEMINI_MODEL="models/gemini-verified",
    OPENROUTER_API_KEY="openrouter-key",
    OPENROUTER_MODEL="openai/gpt-4.1-mini",
)
def test_start_run_persists_explicit_openrouter_provider_and_model(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured fixture",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={
            "planner": {"kind": "gemini.v1", "fallback": {"kind": "fixture_plan.v1"}}
        },
    )
    task = Mock(id="celery-task-1")

    with patch("apps.runs.views.execute_run.delay", return_value=task):
        response = client.post(
            reverse("runs:start", kwargs={"journey_id": journey.id}),
            {"planner_provider": "openrouter"},
        )

    run = Run.objects.get(journey=journey)
    assert response.status_code == 302
    assert run.planner_provider == "openrouter"
    assert run.planner_model == "openai/gpt-4.1-mini"


@override_settings(GEMINI_API_KEY="", GEMINI_MODEL="", OPENROUTER_API_KEY="", OPENROUTER_MODEL="")
def test_start_run_rejects_unconfigured_openrouter_provider(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured fixture",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={
            "planner": {"kind": "gemini.v1", "fallback": {"kind": "fixture_plan.v1"}}
        },
    )

    response = client.post(
        reverse("runs:start", kwargs={"journey_id": journey.id}),
        {"planner_provider": "openrouter"},
        follow=True,
    )

    assert response.status_code == 200
    assert Run.objects.filter(journey=journey).count() == 0
    assert "OpenRouter is not configured" in response.content.decode()


def test_run_detail_shows_persisted_run(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured fixture",
        goal="Complete a configured keyboard-only fixture journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )
    run = Run.objects.create(journey=journey)

    response = client.get(reverse("runs:detail", kwargs={"run_id": run.id}))

    assert response.status_code == 200
    assert str(run.id) in response.content.decode()


def test_run_detail_marks_terminal_issue_screenshot_and_exposes_gallery(client, db) -> None:
    journey = Journey.objects.create(
        name="Keyboard barrier fixture",
        goal="Detect a keyboard barrier without false completion.",
        start_url="http://127.0.0.1:8001/broken/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )
    run = Run.objects.create(
        journey=journey,
        status=RunStatus.SUCCEEDED,
        outcome=JourneyOutcome.BLOCKED,
        terminal_reason="KEYBOARD_TARGET_NOT_REACHABLE",
    )
    step = RunStep.objects.create(
        run=run,
        step_number=5,
        evidence={
            "proposed_action": {"action": "tab", "purpose": "attempt to focus the slot"},
            "policy_decision": {"outcome": "approved", "code": "ACTION_ALLOWED"},
            "action_result": {"status": "effect_observed"},
        },
    )
    RunArtifact.objects.create(
        run=run,
        step=step,
        kind="screenshot_before",
        relative_path="runs/example/step-05-before.png",
        sha256="a" * 64,
    )
    RunArtifact.objects.create(
        run=run,
        step=step,
        kind="screenshot_after",
        relative_path="runs/example/step-05-after.png",
        sha256="b" * 64,
    )

    response = client.get(reverse("runs:detail", kwargs={"run_id": run.id}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "The evaluation stopped at a keyboard barrier" in content
    assert content.count("Issue evidence") == 1
    assert 'id="evidence-viewer"' in content
    assert "ArrowLeft" in content
    assert "ArrowRight" in content


def test_run_list_explains_the_purpose_of_an_evaluation_run(client, db) -> None:
    response = client.get(reverse("runs:list"))

    assert response.status_code == 200
    assert "checks one approved digital journey" in response.content.decode()


def test_run_list_identifies_the_planner_used_for_each_run(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured fixture",
        goal="Complete an approved keyboard journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )
    Run.objects.create(
        journey=journey,
        planner_provider=PlannerProvider.GEMINI,
        planner_model="models/gemini-verified",
    )
    Run.objects.create(
        journey=journey,
        planner_provider=PlannerProvider.OPENROUTER,
        planner_model="openai/gpt-oss-20b",
    )
    Run.objects.create(
        journey=journey,
        planner_provider=PlannerProvider.GROQ,
        planner_model="openai/gpt-oss-20b",
    )
    Run.objects.create(journey=journey, planner_provider=PlannerProvider.FIXTURE)

    response = client.get(reverse("runs:list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Planner used" in content
    assert "Gemini" in content
    assert "OpenRouter" in content
    assert "Groq" in content
    assert "Deterministic fixture" in content


def test_run_detail_labels_a_deterministic_gemini_contingency(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured Gemini journey",
        goal="Complete an approved keyboard journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )
    run = Run.objects.create(
        journey=journey,
        status=RunStatus.SUCCEEDED,
        outcome=JourneyOutcome.COMPLETED,
        planner_metadata={
            "kind": "gemini.v1",
            "model": "models/account-verified",
            "calls": 0,
            "fallback_used": True,
            "fallback_reason": "GEMINI_PREFLIGHT_REQUIRED",
            "fallback_kind": "fixture_plan.v1",
        },
    )

    response = client.get(reverse("runs:detail", kwargs={"run_id": run.id}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Deterministic contingency used" in content
    assert "GEMINI_PREFLIGHT_REQUIRED" in content


def test_run_detail_labels_a_live_groq_run(client, db) -> None:
    journey = Journey.objects.create(
        name="Configured Groq journey",
        goal="Complete an approved keyboard journey.",
        start_url="http://127.0.0.1:8001/accessible/index.html",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )
    run = Run.objects.create(
        journey=journey,
        planner_provider=PlannerProvider.GROQ,
        planner_model="openai/gpt-oss-20b",
        planner_metadata={
            "provider_label": "Groq",
            "model": "openai/gpt-oss-20b",
            "calls": 4,
        },
    )

    response = client.get(reverse("runs:detail", kwargs={"run_id": run.id}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Live Groq" in content
    assert "Deterministic fixture planner" not in content
