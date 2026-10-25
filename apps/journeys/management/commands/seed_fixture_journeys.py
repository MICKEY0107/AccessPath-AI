"""Seed versioned local-fixture journeys from data, not application code."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.journeys.models import Journey


class Command(BaseCommand):
    help = "Create or update the local clinic fixture journeys from their versioned manifest."

    def handle(self, *args: object, **options: object) -> None:
        manifest_path = Path(settings.BASE_DIR) / "fixtures" / "clinic" / "journey-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CommandError(f"Fixture manifest was not found: {manifest_path}") from error
        except json.JSONDecodeError as error:
            raise CommandError(f"Fixture manifest is not valid JSON: {error}") from error

        if manifest.get("schema_version") != "journey-manifest.v1":
            raise CommandError("Unsupported fixture manifest schema version.")

        fixture_base_url = settings.FIXTURE_ALLOWED_ORIGINS[0].rstrip("/")
        for item in manifest.get("journeys", []):
            key = item.get("key")
            if not key:
                raise CommandError("Every fixture journey needs a stable key.")
            allowed_origins = [
                origin.format(fixture_base_url=fixture_base_url)
                for origin in item["allowed_origins"]
            ]
            journey, created = Journey.objects.update_or_create(
                name=item["name"],
                defaults={
                    "goal": item["goal"],
                    "start_url": urljoin(f"{fixture_base_url}/", item["start_path"].lstrip("/")),
                    "execution_mode": item["execution_mode"],
                    "allowed_origins": allowed_origins,
                    "completion_policy": item["completion_policy"],
                    "evaluation_config": item["evaluation_config"],
                    "is_active": True,
                },
            )
            state = "Created" if created else "Updated"
            self.stdout.write(f"{state} fixture journey {key}: {journey.pk}")
