from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.management import call_command
from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .setup_checks import run_checks, summary


def _getting_started(user) -> list[dict]:
    """The first-time checklist; each step is ticked from what already exists."""
    from django.conf import settings

    from apps.codebase.models import RepoBinding
    from apps.journeys.models import Journey
    from apps.runs.model_settings import saved_for
    from apps.runs.models import Run

    journeys = Journey.objects.filter(is_active=True)
    has_model = bool(
        settings.GROQ_API_KEY
        or settings.GEMINI_API_KEY
        or settings.OPENROUTER_API_KEY
        or settings.OLLAMA_BASE_URL
        or saved_for(user)
    )
    return [
        {
            "title": "Load the demo",
            "done": journeys.exists(),
            "text": "Twelve demo journeys on a bundled clinic site, with known results.",
            "action": "seed",
        },
        {
            "title": "Run a journey",
            "done": Run.objects.filter(status="succeeded").exists(),
            "text": "Choose “Scripted plan” to run without any AI key.",
            "url": reverse("runs:list") + "#journeys-title",
        },
        {
            "title": "Link the code",
            "done": RepoBinding.objects.filter(owner=user).exists(),
            "text": "Use the demo repository, or clone your own from GitHub, GitLab or Bitbucket.",
            "url": reverse("codebase:page"),
        },
        {
            "title": "Choose an AI model",
            "done": has_model,
            "text": "Groq, Gemini, OpenRouter or a local Ollama model; keys can be "
            "remembered, encrypted.",
            "url": reverse("runs:model_settings"),
        },
        {
            "title": "Tune the rules",
            "done": journeys.exclude(rule_config={}).exists(),
            "text": "Pick a preset, turn rules off with a reason, or add your team's own rules.",
            "url": reverse("runs:rules"),
        },
    ]


def home(request: HttpRequest) -> HttpResponse:
    """Overview: what AccessPath does and a getting-started checklist."""
    steps = _getting_started(request.user)
    return render(
        request,
        "core/home.html",
        {"steps": steps, "steps_done": sum(step["done"] for step in steps)},
    )


def load_demo(request: HttpRequest) -> HttpResponse:
    """Seed the demo journeys and give this person the bundled demo repository."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    from io import StringIO

    from apps.codebase.demo import ensure_demo_binding

    # Staff refresh the demo journeys; everyone else only adds the ones that are missing,
    # so nobody's edits to an existing journey are undone.
    options = {} if request.user.is_staff else {"only_missing": True}
    call_command("seed_fixture_journeys", stdout=StringIO(), **options)
    binding, linked = ensure_demo_binding(request.user)
    if binding.status == "ready" and linked:
        messages.success(
            request,
            f"Loaded the demo: {linked} journeys, linked to your demo repository. "
            "Run one with “Scripted plan” to see a report without any AI key.",
        )
    elif binding.status == "ready":
        messages.success(
            request,
            "The demo journeys are ready. They are already linked to another repository, "
            "so their reports show code only to the person who linked it.",
        )
    else:
        messages.error(
            request, f"The demo journeys loaded, but the demo repository failed: {binding.error}"
        )
    return redirect(reverse("runs:list") + "#journeys-title")


def status(request: HttpRequest) -> HttpResponse:
    """System status: every part AccessPath needs, and how to fix what is missing."""
    checks = run_checks(request.user)
    groups: dict[str, list] = {}
    for check in checks:
        groups.setdefault(check.group, []).append(check)
    return render(
        request,
        "core/status.html",
        {"groups": groups, "overall": summary(checks)},
    )


@login_not_required
def healthz(request: HttpRequest) -> JsonResponse:
    """Unauthenticated liveness probe; deliberately reveals no deployment details."""
    return JsonResponse({"status": "ok"})


@login_not_required
def readyz(request: HttpRequest) -> JsonResponse:
    """Readiness probe used by a load balancer before sending user traffic."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ready"})
