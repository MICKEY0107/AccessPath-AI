"""Rules page: the shipped catalog and each journey's rule settings."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.journeys.models import Journey
from apps.journeys.rule_settings import (
    SEVERITY_CHOICES,
    RuleSettingsError,
    config_from_form,
    current_config,
    rule_rows,
)
from engine.rules import load_catalog


def rules_page(request: HttpRequest) -> HttpResponse:
    """Show the catalog, or one journey's settings when ?journey= is given."""
    catalog = load_catalog()
    journeys = list(Journey.objects.filter(is_active=True))
    journey = None
    journey_id = request.GET.get("journey", "")
    if journey_id.isdigit():
        journey = next((item for item in journeys if item.id == int(journey_id)), None)
    if journey is None and journeys:
        journey = journeys[0]
    return _render(request, catalog, journeys, journey)


def save_journey_rules(request: HttpRequest, journey_id: int) -> HttpResponse:
    journey = get_object_or_404(Journey, pk=journey_id, is_active=True)
    if request.method != "POST":
        return redirect(f"{reverse('runs:rules')}?journey={journey.id}")
    catalog = load_catalog()
    try:
        config = config_from_form(request.POST, catalog)
    except RuleSettingsError as error:
        messages.error(request, str(error))
        journeys = list(Journey.objects.filter(is_active=True))
        return _render(request, catalog, journeys, journey, status=400)
    journey.rule_config = config.model_dump(mode="json")
    journey.save(update_fields=["rule_config", "updated_at"])
    messages.success(request, f"Saved rule settings for {journey.name}.")
    return redirect(f"{reverse('runs:rules')}?journey={journey.id}")


def _render(request, catalog, journeys, journey, status: int = 200) -> HttpResponse:
    config = current_config(journey.rule_config if journey else {}, catalog)
    return render(
        request,
        "runs/rules.html",
        {
            "catalog": catalog,
            "journeys": journeys,
            "journey": journey,
            "config": config,
            "rows": rule_rows(config, catalog),
            "severity_choices": SEVERITY_CHOICES,
            "ignores": list(enumerate(config.ignores)),
        },
        status=status,
    )
