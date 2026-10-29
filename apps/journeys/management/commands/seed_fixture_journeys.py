"""Seed versioned local-fixture journeys from data, not application code."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.journeys.models import Journey

MANIFESTS = (
    Path("fixtures") / "clinic" / "journey-manifest.json",
    Path("fixtures") / "benchmark" / "journey-manifest.json",
)


def _load(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CommandError(f"Fixture manifest was not found: {path}") from error
    except json.JSONDecodeError as error:
        raise CommandError(f"Fixture manifest is not valid JSON: {error}") from error
    if manifest.get("schema_version") != "journey-manifest.v1":
        raise CommandError("Unsupported fixture manifest schema version.")
    return manifest


class Command(BaseCommand):
    help = (
        "Create or update the local fixture journeys (clinic and benchmark) from their "
        "versioned manifests. Benchmark journeys carry their expected results."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Add journeys that do not exist yet; never change existing ones.",
        )

    def handle(self, *args: object, **options: object) -> None:
        fixture_base_url = settings.FIXTURE_ALLOWED_ORIGINS[0].rstrip("/")
        manifests = [_load(Path(settings.BASE_DIR) / path) for path in MANIFESTS]
        expected_by_key: dict[str, dict] = {}
        for manifest in manifests:
            expected_by_key.update(manifest.get("clinic_expected", {}))
            for item in manifest.get("journeys", []):
                if "expected" in item:
                    expected_by_key[item["key"]] = item["expected"]
        for manifest in manifests:
            for item in manifest.get("journeys", []):
                key = item.get("key")
                if not key:
                    raise CommandError("Every fixture journey needs a stable key.")
                allowed_origins = [
                    origin.format(fixture_base_url=fixture_base_url)
                    for origin in item["allowed_origins"]
                ]
                evaluation_config = {**item["evaluation_config"], "journey_key": key}
                if key in expected_by_key:
                    evaluation_config["benchmark"] = expected_by_key[key]
                exists = Journey.objects.filter(name=item["name"]).exists()
                if options.get("only_missing") and exists:
                    continue
                journey, created = Journey.objects.update_or_create(
                    name=item["name"],
                    defaults={
                        "goal": item["goal"],
                        "start_url": urljoin(
                            f"{fixture_base_url}/", item["start_path"].lstrip("/")
                        ),
                        "execution_mode": item["execution_mode"],
                        "allowed_origins": allowed_origins,
                        "completion_policy": item["completion_policy"],
                        "evaluation_config": evaluation_config,
                        "is_active": True,
                    },
                )
                state = "Created" if created else "Updated"
                self.stdout.write(f"{state} fixture journey {key}: {journey.pk}")
