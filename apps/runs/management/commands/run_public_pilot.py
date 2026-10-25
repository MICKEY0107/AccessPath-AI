"""Run the reviewed Wikipedia keyboard journey as an explicit local proof."""

from __future__ import annotations

import os
from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.journeys.models import Journey
from apps.runs.models import PlannerProvider, Run
from apps.runs.services import execute_configured_run

JOURNEY_NAME = "Wikipedia — find the Web accessibility article"


class Command(BaseCommand):
    help = "Run the approved, read-only Wikipedia keyboard pilot from the local worker."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--provider",
            choices=[
                PlannerProvider.FIXTURE,
                PlannerProvider.GEMINI,
                PlannerProvider.OPENROUTER,
                PlannerProvider.GROQ,
            ],
            default=PlannerProvider.FIXTURE,
        )
        parser.add_argument("--count", type=int, default=None)
        parser.add_argument("--confirm-approved-target", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        if os.environ.get("RUN_APPROVED_LIVE_TESTS", "").lower() != "true":
            raise CommandError("Set RUN_APPROVED_LIVE_TESTS=true for the reviewed live target.")
        if not options["confirm_approved_target"]:
            raise CommandError("Pass --confirm-approved-target for the reviewed live target.")

        provider = options["provider"]
        count = options["count"]
        if count is None:
            count = 5 if provider == PlannerProvider.FIXTURE else 3
        if count < 1:
            raise CommandError("Count must be at least one.")

        model = self._model_for(provider)
        call_command("seed_public_journeys", verbosity=0)
        journey = Journey.objects.get(name=JOURNEY_NAME)
        run_ids: list[str] = []

        for index in range(1, count + 1):
            run = Run.objects.create(
                journey=journey,
                planner_provider=provider,
                planner_model=model,
            )
            result = execute_configured_run(run)
            run.refresh_from_db()
            metadata = run.planner_metadata
            if result.outcome != "completed":
                raise CommandError(
                    f"Public pilot failed: run={run.id} outcome={result.outcome} "
                    f"reason={result.terminal_reason} detail={result.detail}"
                )
            if provider != PlannerProvider.FIXTURE and (
                metadata.get("provider") != provider
                or metadata.get("fallback_used") is not False
                or not isinstance(metadata.get("calls"), int)
                or metadata.get("calls", 0) < 1
            ):
                raise CommandError(
                    f"Live-provider evidence failed: run={run.id} metadata={metadata}"
                )
            run_ids.append(str(run.id))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{index}/{count}] completed provider={provider} "
                    f"steps={result.steps_completed} run={run.id}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Approved Wikipedia pilot passed. provider={provider}; count={count}; "
                f"runs={','.join(run_ids)}"
            )
        )

    @staticmethod
    def _model_for(provider: str) -> str:
        if provider == PlannerProvider.FIXTURE:
            return ""
        settings_by_provider = {
            PlannerProvider.GEMINI: (settings.GEMINI_API_KEY, settings.GEMINI_MODEL),
            PlannerProvider.OPENROUTER: (
                settings.OPENROUTER_API_KEY,
                settings.OPENROUTER_MODEL,
            ),
            PlannerProvider.GROQ: (settings.GROQ_API_KEY, settings.GROQ_MODEL),
        }
        api_key, model = settings_by_provider[provider]
        if not api_key or not model:
            raise CommandError(f"{provider.upper()} is not fully configured.")
        return model
