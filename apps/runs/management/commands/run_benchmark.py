"""Run the benchmark journeys and report the Gate 1 measures."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.journeys.models import Journey
from apps.runs.benchmark import GATE_1, result_for, summarize
from apps.runs.models import PlannerProvider, Run
from apps.runs.services import execute_configured_run, fail_run

LABELS = {
    "trustworthy_rate": "Runs ending in a trustworthy outcome",
    "barrier_precision": "Reported barriers that are real",
    "repeatability": "Same verdict on repeated runs",
    "known_barriers_found": "Known barriers found",
    "within_free_tier_rate": "Runs within free-tier limits",
}


class Command(BaseCommand):
    help = (
        "Run every benchmark journey (seed them with seed_fixture_journeys and start the "
        "fixture server first) and report the Gate 1 measures. Use --provider fixture for "
        "the scripted plans, or a live provider to measure the AI planner."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--provider",
            default=PlannerProvider.FIXTURE,
            choices=[value for value, _label in PlannerProvider.choices],
        )
        parser.add_argument("--model", default="", help="Model id for a live provider.")
        parser.add_argument("--repeat", type=int, default=1, help="Runs per journey (1-5).")
        parser.add_argument("--journeys", nargs="*", default=[], help="Only these journey keys.")
        parser.add_argument("--output", default="", help="Where to write the JSON summary.")

    def handle(self, *args, **options) -> None:
        repeat = options["repeat"]
        if not 1 <= repeat <= 5:
            raise CommandError("--repeat must be between 1 and 5.")
        journeys = [
            journey
            for journey in Journey.objects.filter(is_active=True).order_by("name")
            if journey.evaluation_config.get("benchmark")
            and (
                not options["journeys"]
                or journey.evaluation_config.get("journey_key") in options["journeys"]
            )
        ]
        if not journeys:
            raise CommandError("No benchmark journeys found. Run seed_fixture_journeys first.")
        provider = options["provider"]
        model = options["model"] or {
            PlannerProvider.GEMINI: settings.GEMINI_MODEL,
            PlannerProvider.OPENROUTER: settings.OPENROUTER_MODEL,
            PlannerProvider.GROQ: settings.GROQ_MODEL,
        }.get(provider, "")
        results = []
        for journey in journeys:
            for attempt in range(repeat):
                run = Run.objects.create(
                    journey=journey, planner_provider=provider, planner_model=model
                )
                try:
                    execute_configured_run(run)
                except Exception as error:  # Keep going: one broken run must not stop the rest.
                    fail_run(
                        run,
                        outcome="system_error",
                        reason="BENCHMARK_RUN_FAILED",
                        detail=f"{type(error).__name__}: {error}",
                    )
                run.refresh_from_db()
                result = result_for(run)
                results.append(result)
                mark = "ok " if result.matches else "DIFF"
                self.stdout.write(
                    f"{mark} {result.journey_key} #{attempt + 1}: {result.outcome} "
                    f"{result.confirmed_rules or ''}"
                    + (f" missed {result.missed_rules}" if result.missed_rules else "")
                    + (f" extra {result.extra_rules}" if result.extra_rules else "")
                )
        summary = summarize(results)
        summary["provider"] = provider
        summary["model"] = model
        summary["created_at"] = datetime.now(UTC).isoformat()
        self.stdout.write("")
        metrics = summary["metrics"]
        for name, target in GATE_1.items():
            value = metrics[name]
            shown = "n/a" if value is None else f"{value:.0%}"
            met = summary["gate_1"]["met"][name]
            verdict = "not measured" if met is None else "met" if met else "NOT met"
            self.stdout.write(f"{LABELS[name]:<40} {shown:>6}  (target {target:.0%}, {verdict})")
        self.stdout.write(f"{'Runs matching the expected result':<40} {metrics['expected_result_rate']:.0%}")
        output = Path(
            options["output"]
            or Path(settings.MEDIA_ROOT)
            / "benchmark"
            / f"benchmark-{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        self.stdout.write(f"\nSaved {output}")
