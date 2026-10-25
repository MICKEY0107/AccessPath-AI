import json
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.journeys.models import ExecutionMode, Journey
from engine.contracts import CompletionPolicyV1, TargetPolicyV1


def _manifest() -> dict:
    path = Path(settings.BASE_DIR) / "fixtures" / "public" / "journey-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_manifest_has_valid_target_and_completion_contracts() -> None:
    manifest = _manifest()

    assert manifest["schema_version"] == "public-journey-manifest.v1"
    for journey in manifest["journeys"]:
        TargetPolicyV1.model_validate(journey["target_policy"])
        CompletionPolicyV1.model_validate(journey["completion_policy"])


@pytest.mark.django_db
def test_seed_public_journeys_is_idempotent() -> None:
    output = StringIO()

    call_command("seed_public_journeys", stdout=output)
    call_command("seed_public_journeys", stdout=output)

    journey = Journey.objects.get(name="Wikipedia — find the Web accessibility article")
    assert Journey.objects.filter(name=journey.name).count() == 1
    assert journey.execution_mode == ExecutionMode.PUBLIC_READ_ONLY
    assert journey.start_url == "https://en.wikipedia.org/wiki/Main_Page"
    assert journey.allowed_origins == ["https://en.wikipedia.org"]
    assert journey.evaluation_config["target_policy"]["schema_version"] == "target_policy.v1"
    assert journey.evaluation_config["manifest_version"] == "public-pilot-1.0.0"
    assert journey.evaluation_config["journey_key"] == "wikipedia-web-accessibility-search"
    assert len(journey.completion_policy["signals"]) == 2
