from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command

from engine.gemini import discover_generate_content_models
from engine.planner import GeminiTransientError


def test_preflight_retries_gateway_timeout_without_spending_success_budget(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_MODEL = "models/test-model"
    settings.PLANNER_MAX_TRANSIENT_RETRIES = 2
    settings.PLANNER_TRANSIENT_BACKOFF_SECONDS = 0
    output = StringIO()
    with (
        patch("apps.journeys.management.commands.preflight_gemini.genai.Client") as sdk,
        patch("engine.gemini.GoogleGeminiActionClient.generate_action") as generate,
    ):
        sdk.return_value.models.list.return_value = [
            SimpleNamespace(name="models/test-model", supported_actions=["generateContent"])
        ]
        generate.side_effect = [
            GeminiTransientError("deadline expired"),
            {"action": "tab"},
            {"action": "tab"},
        ]
        call_command("preflight_gemini", calls=2, interval=0, stdout=output)
    assert "GEMINI_PREFLIGHT_PASSED" in output.getvalue()
    assert generate.call_count == 3


def test_model_discovery_uses_api_advertised_capabilities() -> None:
    models = [
        SimpleNamespace(name="models/generate-a", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/embed-a", supported_actions=["embedContent"]),
        SimpleNamespace(name="models/generate-b", supported_actions=["generate_content"]),
    ]

    assert discover_generate_content_models(models) == [
        "models/generate-a",
        "models/generate-b",
    ]


def test_preflight_stops_after_transient_retry_limit(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_MODEL = "models/test-model"
    settings.PLANNER_MAX_TRANSIENT_RETRIES = 2
    settings.PLANNER_TRANSIENT_BACKOFF_SECONDS = 0
    with (
        patch("apps.journeys.management.commands.preflight_gemini.genai.Client") as sdk,
        patch("engine.gemini.GoogleGeminiActionClient.generate_action") as generate,
    ):
        sdk.return_value.models.list.return_value = [
            SimpleNamespace(name="models/test-model", supported_actions=["generateContent"])
        ]
        generate.side_effect = GeminiTransientError("deadline expired")
        with pytest.raises(CommandError, match="attempted_calls=3"):
            call_command("preflight_gemini", calls=1, interval=0, stdout=StringIO())
    assert generate.call_count == 3


def test_preflight_rejects_enter_when_no_element_is_focused(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_MODEL = "models/test-model"
    output = StringIO()
    with (
        patch("apps.journeys.management.commands.preflight_gemini.genai.Client") as sdk,
        patch("engine.gemini.GoogleGeminiActionClient.generate_action") as generate,
    ):
        sdk.return_value.models.list.return_value = [
            SimpleNamespace(name="models/test-model", supported_actions=["generateContent"])
        ]
        generate.return_value = {
            "action": "enter",
            "target_hint": "start-booking",
            "purpose": "open the first link",
        }

        with pytest.raises(CommandError, match="GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE"):
            call_command("preflight_gemini", calls=1, interval=0, stdout=output)

    assert generate.call_count == 1


def test_preflight_rejects_type_when_focused_element_is_not_editable(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_MODEL = "models/test-model"
    with (
        patch("apps.journeys.management.commands.preflight_gemini.genai.Client") as sdk,
        patch("engine.gemini.GoogleGeminiActionClient.generate_action") as generate,
    ):
        sdk.return_value.models.list.return_value = [
            SimpleNamespace(name="models/test-model", supported_actions=["generateContent"])
        ]
        def semantic_response(*, observation, **_):
            if observation.focused_element is None:
                return {"action": "tab"}
            return {
                "action": "type",
                "value": "Asha Test",
                "target_hint": "name",
                "purpose": "fill the name field",
            }

        generate.side_effect = semantic_response

        with pytest.raises(CommandError, match="GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE"):
            call_command("preflight_gemini", calls=2, interval=0, stdout=StringIO())

    assert generate.call_count == 2


def test_preflight_rejects_activation_of_the_wrong_focused_control(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_MODEL = "models/test-model"
    with (
        patch("apps.journeys.management.commands.preflight_gemini.genai.Client") as sdk,
        patch("engine.gemini.GoogleGeminiActionClient.generate_action") as generate,
    ):
        sdk.return_value.models.list.return_value = [
            SimpleNamespace(name="models/test-model", supported_actions=["generateContent"])
        ]

        def semantic_response(*, observation, **_):
            if observation.focused_element is None:
                return {"action": "tab"}
            return {
                "action": "enter",
                "target_hint": "Review appointment",
                "purpose": "open the review page",
            }

        generate.side_effect = semantic_response

        with pytest.raises(CommandError, match="GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE"):
            call_command("preflight_gemini", calls=2, interval=0, stdout=StringIO())

    assert generate.call_count == 2


def test_preflight_refuses_to_run_without_an_api_key(settings) -> None:
    settings.GEMINI_API_KEY = ""

    with pytest.raises(CommandError, match="GEMINI_API_KEY_NOT_CONFIGURED"):
        call_command("preflight_gemini", calls=1)
