import base64
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters
from django.views.static import serve as static_serve

from apps.journeys.models import Journey
from apps.journeys.real_sites import RealSiteJourneyForm

from .credentials import scrub, seal_api_key, validate_api_key, validate_model
from .model_settings import saved_for, saved_key
from .models import JourneyOutcome, PlannerProvider, Run
from .report import build_report, can_view_run, report_json
from .tasks import execute_run

ISSUE_OUTCOMES = {
    JourneyOutcome.BLOCKED,
    JourneyOutcome.ENVIRONMENT_BLOCKED,
    JourneyOutcome.SAFETY_STOPPED,
    JourneyOutcome.AGENT_ERROR,
    JourneyOutcome.SYSTEM_ERROR,
}

TERMINAL_REASON_LABELS = {
    "KEYBOARD_TARGET_NOT_REACHABLE": "A control the task needs cannot be reached with the "
    "keyboard.",
    "KEYBOARD_TARGET_NOT_OPERABLE": "A control the task needs does not respond to Enter or Space.",
    "KEYBOARD_TRAP_CONFIRMED": "Keyboard focus is trapped and cannot leave a component.",
    "BARRIER_NOT_CONFIRMED": "A suspected barrier was re-checked and not confirmed.",
    "COMPLETION_POLICY_SATISFIED": "The declared booking confirmation was verified.",
    "REPEATED_FOCUS_CYCLE": "The evaluator stopped after the configured focus cycle repeated.",
    "REPEATED_ACTION_NO_PROGRESS": (
        "The AI kept pressing the same key on the same control with no effect, so the run "
        "stopped early."
    ),
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


def run_list(
    request: HttpRequest, real_site_form: RealSiteJourneyForm | None = None
) -> HttpResponse:
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

    planner_options = _planner_options(request.user)
    return render(
        request,
        "runs/list.html",
        {
            "journeys": Journey.objects.filter(is_active=True),
            "runs": runs[:20],
            "planner_options": planner_options,
            "stats": {
                "total_runs": Run.objects.count(),
                "completed_runs": Run.objects.filter(outcome=JourneyOutcome.COMPLETED).count(),
                "server_planners": sum(1 for option in planner_options if option["has_server_key"]),
            },
            "run_filter_journeys": Journey.objects.filter(pk__in=Run.objects.values("journey_id"))
            .order_by("name")
            .distinct(),
            "provider_filter_options": Run._meta.get_field("planner_provider").choices,
            "status_filter_options": Run._meta.get_field("status").choices,
            "outcome_filter_options": Run._meta.get_field("outcome").choices,
            "selected_filters": selected_filters,
            "selected_journey_id": selected_journey_id,
            "filters_active": selected_journey_id is not None or any(selected_filters.values()),
            "real_site_form": real_site_form or RealSiteJourneyForm(),
            "real_site_form_open": real_site_form is not None,
        },
        status=400 if real_site_form is not None else 200,
    )


def create_real_site_journey(request: HttpRequest) -> HttpResponse:
    """Add a read-only journey on a live public website from the dashboard."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = RealSiteJourneyForm(request.POST)
    if not form.is_valid():
        return run_list(request, real_site_form=form)
    try:
        journey = form.create_journey()
    except ValidationError as error:
        form.add_error(None, error)
        return run_list(request, real_site_form=form)
    messages.success(request, f"Added {journey.name}. Choose a live planner below to evaluate it.")
    return redirect(f"{reverse('runs:list')}#journey-{journey.id}")


def remove_real_site_journey(request: HttpRequest, journey_id: int) -> HttpResponse:
    """Hide a dashboard-added journey; its past runs and evidence are kept."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    if not journey.is_real_site:
        messages.error(request, "Only journeys you added for a real website can be removed here.")
        return redirect(reverse("runs:list"))
    journey.is_active = False
    journey.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Removed {journey.name}. Its past runs are still listed.")
    return redirect(reverse("runs:list"))


@sensitive_post_parameters("api_key")
def start_run(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    selected_provider = request.POST.get("planner_provider") or _default_provider_for(journey)
    options = {option["value"]: option for option in _planner_options(request.user)}
    selected_option = options.get(selected_provider)
    if selected_option is None:
        messages.error(request, "Select a supported planner provider.")
        return redirect(reverse("runs:list"))
    if selected_provider == PlannerProvider.FIXTURE and not journey.has_fixture_plan:
        messages.error(
            request,
            "This journey has no scripted plan to replay. Choose an AI provider: Groq, Gemini, "
            "OpenRouter or Local Ollama.",
        )
        return redirect(reverse("runs:list"))

    user_api_key = ""
    model = ""
    credential_source = "environment"
    if selected_option["live"]:
        user_api_key = request.POST.get("api_key", "").strip()
        if user_api_key:
            credential_source = "user_supplied"
        elif selected_option["needs_key"]:
            user_api_key = saved_key(request.user, selected_provider)
            credential_source = "saved" if user_api_key else "environment"
        else:
            credential_source = "none"
        model = (
            request.POST.get("planner_model", "").strip()
            or selected_option["saved_model"]
            or selected_option["model"]
        )
        problem = validate_api_key(user_api_key) if user_api_key else None
        if problem is None and model:
            problem = validate_model(model)
        if problem is None and not selected_option["configured"]:
            problem = selected_option["setup_message"]
        if (
            problem is None
            and selected_option["needs_key"]
            and not (user_api_key or selected_option["has_server_key"])
        ):
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
        planner_metadata={
            **({"credential_source": credential_source} if selected_option["live"] else {}),
            "started_by": request.user.pk,
        },
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


def _planner_options(user=None) -> list[dict[str, object]]:
    """Describe each provider; a live one runs with a typed, saved, or server key.

    Only whether a server or saved key exists is exposed (with its masked hint),
    never the key itself.
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
        (
            PlannerProvider.OLLAMA,
            "Local Ollama",
            "A model on your own machine: no API key, and nothing leaves the computer.",
            "",
            settings.OLLAMA_MODEL,
            "llama3.1:8b",
        ),
    ]
    saved = saved_for(user)
    options: list[dict[str, object]] = []
    for value, label, description, server_key, server_model, example_model in live_providers:
        item = saved.get(value)
        is_ollama = value == PlannerProvider.OLLAMA
        options.append(
            {
                "value": value,
                "label": label,
                "description": description,
                "live": True,
                "configured": bool(settings.OLLAMA_BASE_URL) if is_ollama else True,
                "needs_key": not is_ollama,
                "has_server_key": bool(server_key),
                "saved_hint": item.key_hint if item and item.encrypted_key else "",
                "saved_model": item.default_model if item else "",
                "preferred": bool(item and item.is_preferred),
                "model": server_model,
                "model_example": (item.default_model if item else "")
                or server_model
                or example_model,
                "setup_message": (
                    "Ollama is not configured on this server. Set OLLAMA_BASE_URL and run "
                    "`ollama serve`."
                    if is_ollama
                    else f"{label.removeprefix('Live ')} is not configured. Enter an API key for "
                    f"this run, save one under Models, or set {value.upper()}_API_KEY in the "
                    "server .env."
                ),
            }
        )
    options.append(
        {
            "value": PlannerProvider.FIXTURE,
            "label": "Scripted plan (no AI)",
            "description": (
                "Replays the journey's reviewed plan: repeatable, needs no key, and is never "
                "counted as AI evidence."
            ),
            "live": False,
            "configured": True,
            "needs_key": False,
            "has_server_key": False,
            "saved_hint": "",
            "saved_model": "",
            "preferred": False,
            "model": "",
            "model_example": "",
            "setup_message": "",
        }
    )
    return options


FAILURE_KIND_LABELS = {
    "site_barrier": "the website: a keyboard barrier was confirmed by a re-check",
    "agent_failure": "the AI planner: the site was re-checked and not blamed",
    "provider_failure": "the AI provider: the planner stopped before the task could be judged",
    "environment": "the environment: a safety rule or the network stopped the run",
}


def _load_run(run_id, viewer=None) -> Run:
    run = get_object_or_404(
        Run.objects.select_related("journey").prefetch_related(
            "steps", "artifacts__step", "findings"
        ),
        pk=run_id,
    )
    if not can_view_run(run, viewer):
        raise Http404("This run used a saved sign-in; only the person who started it can see it.")
    return run


def evidence_file(request: HttpRequest, path: str) -> HttpResponse:
    """Screenshots and other evidence, with the same visibility as their run."""
    parts = path.split("/")
    if len(parts) >= 2 and parts[0] == "runs":
        try:
            run_id = UUID(parts[1])
        except ValueError:
            raise Http404 from None
        run = Run.objects.filter(pk=run_id).only("planner_metadata").first()
        if run is not None and not can_view_run(run, request.user):
            raise Http404
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


def run_detail(request: HttpRequest, run_id) -> HttpResponse:
    run = _load_run(run_id, request.user)
    return render(
        request,
        "runs/detail.html",
        {
            "run": run,
            "report": build_report(run, request.user),
            "recent_runs": Run.objects.filter(journey=run.journey).order_by("-created_at")[:10],
            "run_brief": describe_run(run),
            "failure_kind_label": FAILURE_KIND_LABELS.get(run.failure_kind, run.failure_kind),
            "evidence_artifacts": build_evidence_artifacts(run),
        },
    )


def export_report_json(request: HttpRequest, run_id) -> HttpResponse:
    """Download the report as JSON for other tools."""
    run = _load_run(run_id, request.user)
    response = JsonResponse(
        report_json(build_report(run, request.user)), json_dumps_params={"indent": 2}
    )
    response["Content-Disposition"] = f'attachment; filename="accesspath-report-{run.id}.json"'
    return response


MAX_EXPORT_IMAGES = 6
MAX_EXPORT_IMAGE_BYTES = 2_000_000


def _embedded_screenshots(run: Run, steps: set[int]) -> list[dict[str, str]]:
    images = []
    for artifact in run.artifacts.all():
        if len(images) >= MAX_EXPORT_IMAGES:
            break
        if artifact.kind != "screenshot_after" or artifact.step is None:
            continue
        if artifact.step.step_number not in steps:
            continue
        path = settings.MEDIA_ROOT / artifact.relative_path
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_EXPORT_IMAGE_BYTES:
            continue
        images.append(
            {
                "step": str(artifact.step.step_number),
                "src": "data:image/png;base64," + base64.b64encode(data).decode("ascii"),
            }
        )
    return images


def export_report_html(request: HttpRequest, run_id) -> HttpResponse:
    """Download a standalone HTML report a product manager can open or forward."""
    run = _load_run(run_id, request.user)
    report = build_report(run, request.user)
    steps = {row["step_number"] for row in report["findings"] if row["step_number"]}
    html = render_to_string(
        "runs/report_export.html",
        {
            "run": run,
            "report": report,
            "screenshots": _embedded_screenshots(run, steps),
            "report_data": report_json(report),
        },
    )
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="accesspath-report-{run.id}.html"'
    return response


def map_to_code(request: HttpRequest, run_id) -> HttpResponse:
    """Re-map a run's findings to its journey's repository (rule-based, no AI)."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from .code_mapping import map_run_findings

    run = _load_run(run_id, request.user)
    binding = run.journey.repo_binding
    if binding is not None and binding.owner_id != request.user.pk:
        messages.error(
            request, "Only the person who linked this repository can map findings to it."
        )
        return redirect(reverse("runs:detail", kwargs={"run_id": run.id}))
    mapped = map_run_findings(run, use_ai=False)
    if mapped:
        messages.success(
            request, f"Mapped {mapped} finding(s) to {run.journey.repo_binding.short_name}."
        )
    else:
        messages.error(
            request, "Link this journey to an analysed repository on the Code page first."
        )
    return redirect(f"{reverse('runs:detail', kwargs={'run_id': run.id})}#panel-findings")


def verify_fix_view(request: HttpRequest, finding_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from engine.fix_verify import can_verify

    from .models import Finding
    from .tasks import verify_fix

    finding = get_object_or_404(
        Finding.objects.select_related("run__journey__repo_binding"), pk=finding_id
    )
    binding = finding.run.journey.repo_binding
    if binding is None or binding.owner_id != request.user.pk:
        messages.error(request, "Only the person who linked this repository can verify its fixes.")
        return redirect(reverse("runs:detail", kwargs={"run_id": finding.run_id}))
    data = dict(finding.data or {})
    locations = data.get("locations") or {}
    if not can_verify(locations.get("fix")):
        messages.error(request, "Only fixes to the project's fixture pages can be verified here.")
    else:
        locations["verification"] = {"status": "running", "detail": "Re-running on a copy…"}
        data["locations"] = locations
        finding.data = data
        finding.save(update_fields=["data"])
        try:
            verify_fix.delay(finding.pk)
        except Exception:
            locations["verification"] = {
                "status": "error",
                "detail": "The worker is not running, so the fix could not be verified.",
            }
            data["locations"] = locations
            finding.data = data
            finding.save(update_fields=["data"])
            messages.error(request, "The worker is not running, so the fix could not be verified.")
    return redirect(f"{reverse('runs:detail', kwargs={'run_id': finding.run_id})}#panel-fixes")
