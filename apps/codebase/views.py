"""Active codebase page: bind a repository to a live site and analyse it."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters

from apps.journeys.models import Journey
from apps.runs.credentials import seal_api_key, validate_api_key
from engine.code_index import load_index
from engine.repo_clone import RepoCloneError, validate_branch, validate_repo_url
from engine.rules import load_catalog

from .demo import ensure_demo_binding
from .models import RepoBinding, RepoStatus
from .services import analyze_binding, remove_binding_files
from .tasks import analyze_repository

PATTERN_RULES = {pattern: rule for rule in load_catalog().rules for pattern in rule.code_patterns}


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""


def codebase_page(request: HttpRequest) -> HttpResponse:
    bindings = list(RepoBinding.objects.filter(owner=request.user))
    active = None
    chosen = request.GET.get("binding", "")
    if chosen.isdigit():
        active = next((item for item in bindings if item.pk == int(chosen)), None)
    if active is None and bindings:
        active = bindings[0]
    patterns = []
    if active is not None and active.status == RepoStatus.READY and active.index_path.is_file():
        for item in load_index(active.index_path).get("patterns", [])[:40]:
            rule = PATTERN_RULES.get(item["kind"])
            patterns.append({**item, "rule": rule, "label": item["kind"].replace("_", " ")})
    journeys = list(Journey.objects.filter(is_active=True))
    return render(
        request,
        "codebase/code.html",
        {
            "bindings": bindings,
            "active": active,
            "patterns": patterns,
            "journeys": journeys,
            "allowed_hosts": settings.REPO_ALLOWED_HOSTS,
            "has_demo": any(item.is_bundled for item in bindings),
            "refresh": active is not None
            and active.status in {RepoStatus.PENDING, RepoStatus.CLONING},
        },
    )


def _queue(request: HttpRequest, binding: RepoBinding, token: str) -> None:
    try:
        if token:
            analyze_repository.delay(binding.pk, credential_token=seal_api_key(token))
        else:
            analyze_repository.delay(binding.pk)
    except Exception:
        binding.status = RepoStatus.FAILED
        binding.error = "The worker is not running, so the repository could not be analysed."
        binding.save(update_fields=["status", "error", "updated_at"])
        messages.error(request, binding.error)


@sensitive_post_parameters("token")
def add_binding(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    token = request.POST.get("token", "").strip()
    live_site_url = request.POST.get("live_site_url", "").strip()
    try:
        repo_url = validate_repo_url(
            request.POST.get("repo_url", ""),
            settings.REPO_ALLOWED_HOSTS,
            allow_file_urls=settings.REPO_ALLOW_FILE_URLS,
        )
        branch = validate_branch(request.POST.get("branch", ""))
    except RepoCloneError as error:
        messages.error(request, str(error))
        return redirect(reverse("codebase:page"))
    problem = validate_api_key(token) if token else None
    if (
        problem is None
        and live_site_url
        and urlparse(live_site_url).scheme not in {"http", "https"}
    ):
        problem = "The live site address must start with http:// or https://."
    if problem:
        messages.error(request, problem.replace("API key", "access token"))
        return redirect(reverse("codebase:page"))
    binding = RepoBinding.objects.create(
        owner=request.user,
        repo_url=repo_url.removesuffix(".git") if repo_url.startswith("https://") else repo_url,
        branch=branch,
        live_site_url=live_site_url,
    )
    linked = _link_journeys(request, binding)
    _queue(request, binding, token)
    note = f" Linked {linked} journey{'s' if linked != 1 else ''}." if linked else ""
    messages.success(request, f"Cloning {binding.short_name}. The token was not stored.{note}")
    return redirect(f"{reverse('codebase:page')}?binding={binding.pk}")


def _link_journeys(request: HttpRequest, binding: RepoBinding) -> int:
    chosen = {int(value) for value in request.POST.getlist("journeys") if value.isdigit()}
    journeys = Journey.objects.filter(is_active=True).select_related("repo_binding")
    if chosen:
        selected = [journey for journey in journeys if journey.pk in chosen]
    elif binding.live_site_url:
        origin = _origin(binding.live_site_url)
        selected = [journey for journey in journeys if _origin(journey.start_url) == origin]
    else:
        selected = []
    linked = 0
    for journey in selected:
        current = journey.repo_binding
        if current is not None and current.pk != binding.pk and current.owner_id != request.user.pk:
            continue  # Never take over a journey someone else linked to their repository.
        journey.repo_binding = binding
        journey.save(update_fields=["repo_binding", "updated_at"])
        linked += 1
    return linked


@sensitive_post_parameters("token")
def reanalyze_binding(request: HttpRequest, binding_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    binding = get_object_or_404(RepoBinding, pk=binding_id, owner=request.user)
    if binding.is_bundled:
        analyze_binding(binding)  # A local copy: quick, and needs no worker.
        messages.success(request, "Refreshed the demo copy.")
        return redirect(f"{reverse('codebase:page')}?binding={binding.pk}")
    token = request.POST.get("token", "").strip()
    if token and validate_api_key(token):
        messages.error(request, "The access token must not contain spaces.")
    else:
        binding.status = RepoStatus.PENDING
        binding.save(update_fields=["status", "updated_at"])
        _queue(request, binding, token)
        messages.success(request, f"Pulling the latest commit of {binding.short_name}.")
    return redirect(f"{reverse('codebase:page')}?binding={binding.pk}")


def use_demo(request: HttpRequest) -> HttpResponse:
    """Add the bundled demo repository for this person and link the demo journeys."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    binding, linked = ensure_demo_binding(request.user)
    if binding.status == RepoStatus.READY and not linked:
        messages.success(
            request,
            "Your demo repository is ready, but the demo journeys are already linked to another "
            "repository; link them from “Journeys using this repository” if they are yours.",
        )
    elif binding.status == RepoStatus.READY:
        messages.success(
            request,
            f"The demo repository is ready and linked to {linked} demo journey"
            f"{'s' if linked != 1 else ''}. Run one, then open its report to see where to fix.",
        )
    else:
        messages.error(request, f"The demo copy could not be prepared: {binding.error}")
    return redirect(f"{reverse('codebase:page')}?binding={binding.pk}")


def link_journeys(request: HttpRequest, binding_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    binding = get_object_or_404(RepoBinding, pk=binding_id, owner=request.user)
    Journey.objects.filter(repo_binding=binding).update(repo_binding=None)
    linked = _link_journeys(request, binding)
    messages.success(request, f"{binding.short_name} is now linked to {linked} journey(s).")
    return redirect(f"{reverse('codebase:page')}?binding={binding.pk}")


def remove_binding(request: HttpRequest, binding_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    binding = get_object_or_404(RepoBinding, pk=binding_id, owner=request.user)
    name = binding.short_name
    remove_binding_files(binding)
    binding.delete()
    messages.success(request, f"Removed {name} and deleted its local copy.")
    return redirect(reverse("codebase:page"))
