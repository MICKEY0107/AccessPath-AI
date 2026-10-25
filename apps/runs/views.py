from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

from apps.journeys.models import Journey

from .credentials import scrub, seal_api_key, validate_api_key, validate_model
from .models import JourneyOutcome, PlannerProvider, Run
from .tasks import execute_run

ISSUE_OUTCOMES = {
    JourneyOutcome.BLOCKED,
    JourneyOutcome.ENVIRONMENT_BLOCKED,
    JourneyOutcome.SAFETY_STOPPED,
    JourneyOutcome.AGENT_ERROR,
    JourneyOutcome.SYSTEM_ERROR,
}

TERMINAL_REASON_LABELS = {
    "KEYBOARD_TARGET_NOT_REACHABLE": "Keyboard focus could not reach the appointment time buttons.",
    "COMPLETION_POLICY_SATISFIED": "The declared booking confirmation was verified.",
    "REPEATED_FOCUS_CYCLE": "The evaluator stopped after the configured focus cycle repeated.",
    "REQUEST_METHOD_NOT_ALLOWED": "A prohibited request method was blocked.",
    "NAVIGATION_ORIGIN_NOT_ALLOWED": "Navigation outside the approved origin was blocked.",
    "NAVIGATION_PATH_NOT_ALLOWED": "Navigation outside the approved path was blocked.",
    "POPUP_NOT_ALLOWED": "An unapproved popup was blocked.",
    "DOWNLOAD_NOT_ALLOWED": "An unapproved download was blocked.",
}


def terminal_reason_label(reason: str) -> str:
    """Turn internal terminal codes into short, user-facing explanations."""
    return TERMINAL_REASON_LABELS.get(reason, reason.replace("_", " ").capitalize())


def describe_run(run: Run) -> str:
    """Return a brief, outcome-specific explanation for the run detail page."""
    if run.outcome == JourneyOutcome.COMPLETED:
        return (
            "The configured journey reached its declared completion state using only keyboard "
            "actions. Each step and screenshot below forms the audit trail for that result."
        )
    if run.outcome == JourneyOutcome.BLOCKED:
        return (
            "The evaluation stopped at a keyboard barrier in the declared journey. The evidence "
            "supports reproduction and review; the evaluator stopped safely and did not claim "
            "completion."
        )
    if run.outcome in ISSUE_OUTCOMES:
        return (
            "The evaluation stopped before a verified completion. The red evidence item, when "
            "available, is the final screenshot captured for the reported issue."
        )
    return (
        "The worker is preparing or evaluating this configured journey. This page refreshes while "
        "the run is active and will show an evidence-backed outcome when it finishes."
    )


def build_evidence_artifacts(run: Run) -> list[dict[str, object]]:
    """Prepare durable evidence metadata for the accessible image gallery."""
    artifacts = list(run.artifacts.all())
    issue_artifact_id: int | None = None
    if run.outcome in ISSUE_OUTCOMES:
        issue_artifact_id = next(
            (
                artifact.id
                for artifact in reversed(artifacts)
                if artifact.kind == "screenshot_after" and artifact.step_id is not None
            ),
            None,
        )

    return [
        {
            "id": artifact.id,
            "step_number": artifact.step.step_number if artifact.step else None,
            "kind": artifact.kind.replace("_", " "),
            "url": f"{settings.MEDIA_URL}{artifact.relative_path}",
            "sha256": artifact.sha256,
            "is_issue_evidence": artifact.id == issue_artifact_id,
            "issue_label": (
                f"Issue evidence: {terminal_reason_label(run.terminal_reason)}"
                if artifact.id == issue_artifact_id
                else ""
            ),
        }
        for artifact in artifacts
    ]


def run_list(request: HttpRequest) -> HttpResponse:
    """Show active configured journeys and recent durable runs."""
    runs = Run.objects.select_related("journey")
    selected_filters = {
        "provider": request.GET.get("provider", ""),
        "status": request.GET.get("status", ""),
        "outcome": request.GET.get("outcome", ""),
    }
    selected_journey_id = None
    journey_id = request.GET.get("journey", "")
    if journey_id.isdigit():
        selected_journey_id = int(journey_id)
        runs = runs.filter(journey_id=selected_journey_id)

    valid_providers = {value for value, _label in Run._meta.get_field("planner_provider").choices}
    valid_statuses = {value for value, _label in Run._meta.get_field("status").choices}
    valid_outcomes = {value for value, _label in Run._meta.get_field("outcome").choices}
    if selected_filters["provider"] in valid_providers:
        runs = runs.filter(planner_provider=selected_filters["provider"])
    else:
        selected_filters["provider"] = ""
    if selected_filters["status"] in valid_statuses:
        runs = runs.filter(status=selected_filters["status"])
    else:
        selected_filters["status"] = ""
    if selected_filters["outcome"] in valid_outcomes:
        runs = runs.filter(outcome=selected_filters["outcome"])
    else:
        selected_filters["outcome"] = ""

    return render(
        request,
        "runs/list.html",
        {
            "journeys": Journey.objects.filter(is_active=True),
            "runs": runs[:20],
            "planner_options": _planner_options(),
            "run_filter_journeys": Journey.objects.filter(
                pk__in=Run.objects.values("journey_id")
            )
            .order_by("name")
            .distinct(),
            "provider_filter_options": Run._meta.get_field("planner_provider").choices,
            "status_filter_options": Run._meta.get_field("status").choices,
            "outcome_filter_options": Run._meta.get_field("outcome").choices,
            "selected_filters": selected_filters,
            "selected_journey_id": selected_journey_id,
            "filters_active": selected_journey_id is not None or any(selected_filters.values()),
        },
    )


@sensitive_post_parameters("api_key")
def start_run(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    selected_provider = request.POST.get("planner_provider") or _default_provider_for(journey)
    options = {option["value"]: option for option in _planner_options()}
    selected_option = options.get(selected_provider)
    if selected_option is None:
        messages.error(request, "Select a supported planner provider.")
        return redirect(reverse("runs:list"))

    user_api_key = ""
    model = ""
    if selected_option["live"]:
        user_api_key = request.POST.get("api_key", "").strip()
        model = request.POST.get("planner_model", "").strip() or selected_option["model"]
        problem = validate_api_key(user_api_key) if user_api_key else None
        if problem is None and model:
            problem = validate_model(model)
        if problem is None and not (user_api_key or selected_option["has_server_key"]):
            problem = selected_option["setup_message"]
        if problem is None and not model:
            problem = "Enter the model to use for this run."
        if problem:
            messages.error(request, problem)
            return redirect(reverse("runs:list"))

    run = Run.objects.create(
        journey=journey,
        planner_provider=selected_provider,
        planner_model=model,
        planner_metadata=(
            {"credential_source": "user_supplied" if user_api_key else "environment"}
            if selected_option["live"]
            else {}
        ),
    )
    try:
        if user_api_key:
            task = execute_run.delay(str(run.id), credential_token=seal_api_key(user_api_key))
        else:
            task = execute_run.delay(str(run.id))
    except Exception as error:
        run.status = "failed"
        run.outcome = "environment_blocked"
        run.terminal_reason = "WORKER_UNAVAILABLE"
        run.error_detail = scrub(f"{type(error).__name__}: {error}", [user_api_key])
        run.save(update_fields=["status", "outcome", "terminal_reason", "error_detail"])
        messages.error(request, "The run could not be queued because the worker is unavailable.")
    else:
        run.celery_task_id = task.id
        run.save(update_fields=["celery_task_id"])
    return redirect(reverse("runs:detail", kwargs={"run_id": run.id}))


def _default_provider_for(journey: Journey) -> str:
    """Choose a safe default that matches the journey's configured planner."""
    planner = journey.evaluation_config.get("planner", {})
    if planner.get("kind") == "fixture_plan.v1":
        return PlannerProvider.FIXTURE
    return PlannerProvider.GEMINI


def _planner_options() -> list[dict[str, object]]:
    """Describe each provider; a live one runs with a typed key or the server's env key.

    Only whether a server key exists is exposed, never the key itself.
    """
    live_providers = [
        (
            PlannerProvider.GEMINI,
            "Live Gemini",
            "Direct Google Gemini structured-action planning.",
            settings.GEMINI_API_KEY,
            settings.GEMINI_MODEL,
            "gemini-2.5-flash",
        ),
        (
            PlannerProvider.OPENROUTER,
            "Live OpenRouter",
            "OpenRouter structured-action planning with an explicitly recorded model.",
            settings.OPENROUTER_API_KEY,
            settings.OPENROUTER_MODEL,
            "openai/gpt-4.1-mini",
        ),
        (
            PlannerProvider.GROQ,
            "Live Groq",
            "Groq LPU structured-action planning — fast, generous free-tier rate limits.",
            settings.GROQ_API_KEY,
            settings.GROQ_MODEL,
            "llama-3.3-70b-versatile",
        ),
    ]
    options: list[dict[str, object]] = [
        {
            "value": value,
            "label": label,
            "description": description,
            "live": True,
            "configured": True,
            "has_server_key": bool(server_key),
            "model": server_model,
            "model_example": server_model or example_model,
            "setup_message": (
                f"{label.removeprefix('Live ')} is not configured. Enter an API key for this "
                f"run, or set {value.upper()}_API_KEY in the server .env."
            ),
        }
        for value, label, description, server_key, server_model, example_model in live_providers
    ]
    options.append(
        {
            "value": PlannerProvider.FIXTURE,
            "label": "Deterministic fixture contingency",
            "description": (
                "Repeatable scripted fixture evidence; never counted as live-model evidence."
            ),
            "live": False,
            "configured": True,
            "has_server_key": False,
            "model": "",
            "model_example": "",
            "setup_message": "",
        }
    )
    return options


def run_detail(request: HttpRequest, run_id) -> HttpResponse:
    run = get_object_or_404(
        Run.objects.select_related("journey").prefetch_related("steps", "artifacts__step"),
        pk=run_id,
    )
    return render(
        request,
        "runs/detail.html",
        {
            "run": run,
            "run_brief": describe_run(run),
            "evidence_artifacts": build_evidence_artifacts(run),
        },
    )
