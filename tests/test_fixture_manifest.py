import json
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

from apps.journeys.models import Journey
from engine.contracts import CompletionPolicyV1


def test_fixture_manifest_is_a_valid_completion_contract() -> None:
    manifest_path = Path(settings.BASE_DIR) / "fixtures" / "clinic" / "journey-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "journey-manifest.v1"
    for journey in manifest["journeys"]:
        CompletionPolicyV1.model_validate(journey["completion_policy"])


def test_seed_fixture_journeys_is_idempotent(db) -> None:
    call_command("seed_fixture_journeys")
    call_command("seed_fixture_journeys")

    accessible = Journey.objects.get(
        name="Clinic appointment booking — keyboard-accessible reference"
    )
    fixture_origin = settings.FIXTURE_ALLOWED_ORIGINS[0].rstrip("/")
    assert accessible.start_url == f"{fixture_origin}/accessible/index.html"
    assert accessible.allowed_origins == [fixture_origin]
    assert accessible.evaluation_config["planner"]["kind"] == "gemini.v1"
    assert accessible.evaluation_config["planner"]["fallback"]["kind"] == "fixture_plan.v1"
    assert Journey.objects.count() == 12
    assert accessible.evaluation_config["benchmark"] == {
        "outcome": "completed",
        "confirmed_rules": [],
    }
    trap = Journey.objects.get(name="Benchmark — cookie dialog keyboard trap")
    assert trap.evaluation_config["benchmark"]["confirmed_rules"] == ["no-keyboard-trap"]
    assert trap.start_url == f"{fixture_origin}/benchmark/cookie-trap.html"


def test_benchmark_manifest_is_valid_and_every_journey_has_expectations() -> None:
    path = Path(settings.BASE_DIR) / "fixtures" / "benchmark" / "journey-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert len(manifest["journeys"]) == 10
    for journey in manifest["journeys"]:
        CompletionPolicyV1.model_validate(journey["completion_policy"])
        assert journey["expected"]["outcome"] in {"completed", "blocked"}
        page = Path(settings.BASE_DIR) / "fixtures" / "clinic" / journey["start_path"].lstrip("/")
        assert page.is_file(), page
