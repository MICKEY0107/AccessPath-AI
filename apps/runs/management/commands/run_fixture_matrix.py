from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.journeys.models import Journey
from apps.runs.models import PlannerProvider, Run
from apps.runs.services import execute_configured_run


class Command(BaseCommand):
    help = (
        "Run a provider-specific Phase 1 fixture matrix. "
        "Only non-fallback outcomes from the selected live provider count as evidence."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--accessible-count", type=int, default=3)
        parser.add_argument("--broken-count", type=int, default=5)
        parser.add_argument(
            "--provider",
            choices=[PlannerProvider.GEMINI, PlannerProvider.OPENROUTER, PlannerProvider.GROQ],
            default=PlannerProvider.GEMINI,
            help="Live provider to verify. Provider selection is never mixed within a matrix.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        accessible_count = options["accessible_count"]
        broken_count = options["broken_count"]
        provider = options["provider"]
        if accessible_count < 0 or broken_count < 0:
            raise CommandError("Matrix counts cannot be negative.")
        if accessible_count + broken_count < 1:
            raise CommandError("At least one matrix case is required.")
        if provider == PlannerProvider.GEMINI:
            api_key = settings.GEMINI_API_KEY
            model = settings.GEMINI_MODEL
            provider_label = "Gemini"
        elif provider == PlannerProvider.GROQ:
            api_key = settings.GROQ_API_KEY
            model = settings.GROQ_MODEL
            provider_label = "Groq"
        else:
            api_key = settings.OPENROUTER_API_KEY
            model = settings.OPENROUTER_MODEL
            provider_label = "OpenRouter"
        if not api_key:
            raise CommandError(
                f"{provider_label.upper()}_API_KEY is required for live matrix evidence."
            )
        if not model:
            raise CommandError(
                f"{provider_label.upper()}_MODEL is required and must come from provider preflight."
            )

        journeys = self._journeys_by_manifest_key()
        cases = (
            [("clinic-accessible-booking", "completed")] * accessible_count
            + [("clinic-keyboard-trap-control", "blocked")] * broken_count
        )
        evidence: list[str] = []

        for index, (journey_key, expected_result) in enumerate(cases, start=1):
            run = Run.objects.create(
                journey=journeys[journey_key],
                planner_provider=provider,
                planner_model=model,
            )
            execute_configured_run(run)
            run.refresh_from_db()
            metadata = run.planner_metadata
            fallback_used = metadata.get("fallback_used", True)
            calls = metadata.get("calls", 0)

            if (
                run.outcome != expected_result
                or fallback_used is not False
                or metadata.get("provider") != provider
                or not isinstance(calls, int)
                or calls < 1
            ):
                raise CommandError(
                    "Matrix evidence failed: "
                    f"run={run.id} journey={journey_key} expected={expected_result} "
                    f"actual={run.outcome} provider={metadata.get('provider')!r} "
                    f"fallback_used={fallback_used} calls={calls}."
                )

            evidence.append(str(run.id))
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{index}/{len(cases)}] {journey_key}: {run.outcome}; "
                    f"live {provider_label} calls={calls}; run={run.id}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Fixture matrix passed with live {provider_label} only. "
                f"accessible={accessible_count}; broken={broken_count}; "
                f"false_completions=0; runs={','.join(evidence)}"
            )
        )

    @staticmethod
    def _journeys_by_manifest_key() -> dict[str, Journey]:
        manifest_path = Path(settings.BASE_DIR) / "fixtures" / "clinic" / "journey-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read fixture manifest: {exc}") from exc

        required = {"clinic-accessible-booking", "clinic-keyboard-trap-control"}
        configured: dict[str, Journey] = {}
        for item in manifest.get("journeys", []):
            key = item.get("key")
            if key in required:
                try:
                    configured[key] = Journey.objects.get(name=item["name"])
                except (Journey.DoesNotExist, KeyError) as exc:
                    raise CommandError(
                        f"Fixture journey {key!r} is not seeded; run seed_fixture_journeys."
                    ) from exc

        missing = required - configured.keys()
        if missing:
            raise CommandError(
                f"Fixture manifest is missing required journeys: {', '.join(sorted(missing))}."
            )
        return configured
