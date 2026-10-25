"""Seed reviewed public read-only journeys from a versioned manifest."""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from pydantic import ValidationError

from apps.journeys.models import ExecutionMode, Journey
from engine.contracts import CompletionPolicyV1, TargetPolicyV1
from engine.target_policy import TargetPolicy


class Command(BaseCommand):
    help = "Create or update approved public read-only journeys."

    def handle(self, *args: object, **options: object) -> None:
        del args, options
        manifest_path = Path(settings.BASE_DIR) / "fixtures" / "public" / "journey-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CommandError(f"Public journey manifest was not found: {manifest_path}") from error
        except json.JSONDecodeError as error:
            raise CommandError(f"Public journey manifest is not valid JSON: {error}") from error

        if manifest.get("schema_version") != "public-journey-manifest.v1":
            raise CommandError("Unsupported public journey manifest schema version.")

        for item in manifest.get("journeys", []):
            try:
                target_policy = TargetPolicyV1.model_validate(item["target_policy"])
                completion_policy = CompletionPolicyV1.model_validate(item["completion_policy"])
                TargetPolicy(target_policy).validate_start_url(item["start_url"])
            except (KeyError, ValidationError, ValueError) as error:
                raise CommandError(
                    f"Public journey {item.get('key', '<unknown>')!r} is invalid: {error}"
                ) from error

            evaluation_config = dict(item.get("evaluation_config", {}))
            evaluation_config["target_policy"] = target_policy.model_dump(mode="json")
            evaluation_config["manifest_version"] = manifest.get("manifest_version", "")
            evaluation_config["journey_key"] = item["key"]
            journey, created = Journey.objects.update_or_create(
                name=item["name"],
                defaults={
                    "goal": item["goal"],
                    "start_url": item["start_url"],
                    "execution_mode": ExecutionMode.PUBLIC_READ_ONLY,
                    "allowed_origins": target_policy.navigation_origins,
                    "completion_policy": completion_policy.model_dump(mode="json"),
                    "evaluation_config": evaluation_config,
                    "is_active": True,
                },
            )
            state = "Created" if created else "Updated"
            self.stdout.write(f"{state} public journey {item['key']}: {journey.pk}")
