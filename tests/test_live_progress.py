"""Steps are saved while a run is still going, so the run page shows progress."""

from __future__ import annotations

import pytest

from apps.journeys.models import Journey
from apps.runs.models import Run, RunStep
from apps.runs.services import execute_configured_run
from engine.executor import KeyboardExecutor

ROOT_JOURNEY = "Clinic appointment booking — keyboard-accessible reference"


@pytest.mark.django_db
def test_steps_are_saved_as_they_happen(settings, tmp_path, monkeypatch) -> None:
    from io import StringIO

    from django.core.management import call_command

    settings.MEDIA_ROOT = tmp_path
    call_command("seed_fixture_journeys", stdout=StringIO())
    journey = Journey.objects.get(name=ROOT_JOURNEY)
    run = Run.objects.create(journey=journey, planner_provider="fixture")
    seen_during_run: list[int] = []
    original = KeyboardExecutor.run_with_planner

    def watching(self, planner, *, goal):
        inner = self.on_step

        def on_step(evidence, artifacts):
            inner(evidence, artifacts)
            # Read from the database the same way the run page does, mid-run.
            from apps.runs.services import sync_orm_allowed

            with sync_orm_allowed():
                seen_during_run.append(RunStep.objects.filter(run=run).count())

        self.on_step = on_step
        return original(self, planner, goal=goal)

    monkeypatch.setattr(KeyboardExecutor, "run_with_planner", watching)
    execute_configured_run(run)
    run.refresh_from_db()
    assert run.outcome == "completed"
    assert seen_during_run[:3] == [1, 2, 3]
    assert RunStep.objects.filter(run=run).count() == len(seen_during_run)
