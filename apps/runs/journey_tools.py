"""Journey settings: saved sign-in, replayable plan, staging writes and baseline.

* A saved sign-in (Playwright storage state) lets a journey test pages behind a login.
  It is encrypted, cut down to the journey's own sites, never shown back, and used only
  by runs its owner starts.
* Record and replay: a successful run's keys become the journey's scripted plan, so it
  can be replayed without AI (a regression test), here or with the command line.
* Staging writes: a journey on a site its owner controls may submit forms (POST to its
  own origin only, a few per run). Off by default and never for seeded demo journeys.
* Baseline: a chosen run whose findings later reports compare against.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.journeys.models import Journey, JourneySession
from engine.session_state import (
    SessionStateError,
    describe,
    limit_to_origins,
    parse_storage_state,
)

from .credentials import encrypt_session
from .models import Run

MAX_UPLOAD = 1_000_000


def _settings_url(journey: Journey) -> str:
    return reverse("runs:journey_settings", args=[journey.pk])


def journey_settings(request: HttpRequest, journey_id: int) -> HttpResponse:
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    session = JourneySession.objects.filter(journey=journey).select_related("owner").first()
    config = journey.evaluation_config or {}
    planner = config.get("planner") or {}
    recorded = config.get("recorded_plan")
    baseline_id = config.get("baseline_run")
    baseline = Run.objects.filter(pk=baseline_id).first() if baseline_id else None
    candidates = Run.objects.filter(journey=journey, status="succeeded").order_by("-created_at")[
        :10
    ]
    return render(
        request,
        "runs/journey_settings.html",
        {
            "journey": journey,
            "session": session,
            "session_is_mine": bool(session and session.owner_id == request.user.pk),
            "recorded": recorded,
            "scripted_only": planner.get("kind") == "fixture_plan.v1",
            "has_plan": journey.has_fixture_plan,
            "staging": config.get("staging") or {},
            "can_stage": journey.is_real_site,
            "baseline": baseline,
            "candidates": candidates,
            "replay_candidates": [run for run in candidates if run.outcome == "completed"],
        },
    )


def save_session(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    existing = JourneySession.objects.filter(journey=journey).first()
    if request.POST.get("remove"):
        if existing and existing.owner_id == request.user.pk:
            existing.delete()
            messages.success(request, "Removed the saved sign-in.")
        else:
            messages.error(request, "Only the person who saved the sign-in can remove it.")
        return redirect(_settings_url(journey))
    if existing and existing.owner_id != request.user.pk:
        messages.error(request, "Someone else saved a sign-in for this journey.")
        return redirect(_settings_url(journey))
    upload = request.FILES.get("state")
    if upload is None or upload.size > MAX_UPLOAD:
        messages.error(
            request, "Choose the session file saved by `accesspath login` (1 MB or less)."
        )
        return redirect(_settings_url(journey))
    try:
        state = limit_to_origins(parse_storage_state(upload.read()), journey.allowed_origins)
    except SessionStateError as error:
        messages.error(request, str(error))
        return redirect(_settings_url(journey))
    if not state["cookies"] and not state["origins"]:
        messages.error(request, "The session has nothing for this journey's sites.")
        return redirect(_settings_url(journey))
    JourneySession.objects.update_or_create(
        journey=journey,
        defaults={
            "owner": request.user,
            "encrypted_state": encrypt_session(json.dumps(state)),
            "summary": describe(state)[:300],
        },
    )
    messages.success(request, f"Saved the sign-in ({describe(state)}). Only your runs use it.")
    return redirect(_settings_url(journey))


def _run_or_404(journey: Journey, run_id: str, **filters) -> Run:
    try:
        pk = UUID(str(run_id))
    except ValueError:
        raise Http404("No such run.") from None
    return get_object_or_404(Run, pk=pk, journey=journey, **filters)


def _signed_in_by_someone_else(request: HttpRequest, journey: Journey) -> bool:
    """Replay plans and staging writes run under the saved sign-in, so only its owner
    may change them while one is saved."""
    session = JourneySession.objects.filter(journey=journey).select_related("owner").first()
    if session is None or session.owner_id == request.user.pk:
        return False
    messages.error(
        request,
        f"{session.owner.get_username()} saved a sign-in for this journey; only they can "
        "change its replay plan or staging writes.",
    )
    return True


def plan_from_run(run: Run) -> list[dict]:
    """The keys a run actually pressed, in order, as scripted plan steps."""
    actions = []
    for step in run.steps.order_by("step_number"):
        executed = (step.evidence or {}).get("executed_action")
        if not executed:
            continue
        action = {"action": executed["action"]}
        for key in ("value", "target_hint", "purpose"):
            if executed.get(key):
                action[key] = executed[key]
        actions.append(action)
    return actions


def save_replay_plan(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    config = dict(journey.evaluation_config or {})
    planner = dict(config.get("planner") or {})
    if planner.get("kind") == "fixture_plan.v1" or config.get("benchmark"):
        messages.error(request, "This journey already has a reviewed scripted plan.")
        return redirect(_settings_url(journey))
    if _signed_in_by_someone_else(request, journey):
        return redirect(_settings_url(journey))
    run = _run_or_404(journey, request.POST.get("run_id", ""))
    if run.outcome != "completed":
        messages.error(request, "Only a run that completed the journey can be replayed.")
        return redirect(_settings_url(journey))
    actions = plan_from_run(run)
    if not actions:
        messages.error(request, "That run has no keyboard steps to replay.")
        return redirect(_settings_url(journey))
    planner["fallback"] = {
        "kind": "fixture_plan.v1",
        "actions": actions,
        "synthetic_values": planner.get("synthetic_values", {}),
    }
    planner.pop("allow_no_fallback", None)
    config["planner"] = planner
    config["recorded_plan"] = {
        "run": str(run.id),
        "steps": len(actions),
        "recorded_at": datetime.now(UTC).isoformat(),
        "by": request.user.get_username(),
        "provider": run.planner_provider,
    }
    journey.evaluation_config = config
    journey.save(update_fields=["evaluation_config", "updated_at"])
    messages.success(
        request,
        f"Saved {len(actions)} keys from that run as the replay plan. Choose “Scripted plan "
        "(no AI)” to replay it.",
    )
    return redirect(_settings_url(journey))


def export_journey_file(request: HttpRequest, journey_id: int) -> HttpResponse:
    """The journey as a file for `python -m accesspath run` (CLI and CI)."""
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    config = journey.evaluation_config or {}
    planner = config.get("planner") or {}
    plan = planner if planner.get("kind") == "fixture_plan.v1" else planner.get("fallback") or {}
    data: dict = {
        "schema_version": "accesspath_journey.v1",
        "name": journey.name,
        "goal": journey.goal,
        "start_url": journey.start_url,
        "allowed_origins": journey.allowed_origins,
        "completion_policy": journey.completion_policy,
        "type_values": plan.get("synthetic_values") or planner.get("synthetic_values") or {},
        "plan": plan.get("actions") or [],
        "rules": journey.rule_config or {},
    }
    if config.get("barrier_check"):
        data["barrier_check"] = config["barrier_check"]
    if config.get("target_policy"):
        data["target_policy"] = config["target_policy"]
    slug = "".join(ch if ch.isalnum() else "-" for ch in journey.name.lower()).strip("-")[:60]
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False), content_type="application/json"
    )
    response["Content-Disposition"] = f'attachment; filename="{slug or "journey"}.json"'
    return response


def save_staging(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    if not journey.is_real_site:
        messages.error(request, "Staging writes are only for websites you added yourself.")
        return redirect(_settings_url(journey))
    if _signed_in_by_someone_else(request, journey):
        return redirect(_settings_url(journey))
    config = dict(journey.evaluation_config or {})
    if request.POST.get("enable") == "on":
        if request.POST.get("confirm") != "on":
            messages.error(request, "Confirm that you control this site and it is not production.")
            return redirect(_settings_url(journey))
        try:
            max_writes = max(1, min(20, int(request.POST.get("max_writes", "5"))))
        except ValueError:
            max_writes = 5
        config["staging"] = {
            "enabled": True,
            "max_writes": max_writes,
            "confirmed_by": request.user.get_username(),
            "confirmed_at": datetime.now(UTC).isoformat(),
        }
        messages.success(
            request, f"Staging writes on: up to {max_writes} form submissions per run."
        )
    else:
        config.pop("staging", None)
        messages.success(request, "Staging writes off: runs are read-only again.")
    journey.evaluation_config = config
    journey.save(update_fields=["evaluation_config", "updated_at"])
    return redirect(_settings_url(journey))


def save_baseline(request: HttpRequest, journey_id: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    config = dict(journey.evaluation_config or {})
    run_id = request.POST.get("run_id", "")
    if not run_id:
        config.pop("baseline_run", None)
        messages.success(request, "Cleared the baseline.")
    else:
        run = _run_or_404(journey, run_id, status="succeeded")
        config["baseline_run"] = str(run.id)
        messages.success(request, "Saved the baseline: reports now show new and fixed findings.")
    journey.evaluation_config = config
    journey.save(update_fields=["evaluation_config", "updated_at"])
    return redirect(_settings_url(journey))
