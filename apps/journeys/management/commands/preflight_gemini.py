from __future__ import annotations

import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from google import genai
from google.genai import types

from engine.contracts import ActionKind, ElementEvidenceV1, PlannerObservationV1
from engine.gemini import GoogleGeminiActionClient, discover_generate_content_models
from engine.planner import GeminiPlanner, PlannerError


class Command(BaseCommand):
    help = "Discover account-available Gemini models and verify bounded structured-action quota."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--model", default="", help="Exact API-advertised model ID to verify.")
        parser.add_argument("--calls", type=int, default=12)
        parser.add_argument("--interval", type=float, default=None)
        parser.add_argument("--list-only", action="store_true")

    def handle(self, *args, **options) -> None:
        del args
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise CommandError("GEMINI_API_KEY_NOT_CONFIGURED")

        calls = options["calls"]
        if calls < 1 or calls > 50:
            raise CommandError("PREFLIGHT_CALLS_MUST_BE_BETWEEN_1_AND_50")
        interval = (
            settings.PLANNER_MIN_CALL_INTERVAL_SECONDS
            if options["interval"] is None
            else options["interval"]
        )
        if interval < 0:
            raise CommandError("PREFLIGHT_INTERVAL_MUST_BE_NON_NEGATIVE")

        sdk_client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.PLANNER_CALL_TIMEOUT_SECONDS * 1000)
            ),
        )
        try:
            available = discover_generate_content_models(sdk_client.models.list())
        except Exception as error:
            raise CommandError(f"GEMINI_MODEL_DISCOVERY_FAILED: {type(error).__name__}") from error

        self.stdout.write("API-advertised generateContent models:")
        for model_name in available:
            self.stdout.write(f"- {model_name}")
        if options["list_only"]:
            return

        selected_model = options["model"] or settings.GEMINI_MODEL
        if not selected_model:
            raise CommandError(
                "GEMINI_MODEL_NOT_SELECTED: choose an exact model ID from the discovered list"
            )
        if selected_model not in available:
            raise CommandError("GEMINI_MODEL_NOT_AVAILABLE_FOR_THIS_KEY")

        planner = GeminiPlanner(
            client=GoogleGeminiActionClient(
                sdk_client,
                min_interval_seconds=interval,
            ),
            model=selected_model,
            max_calls=calls * (
                1 + settings.PLANNER_MAX_429_RETRIES + settings.PLANNER_MAX_TRANSIENT_RETRIES
            ),
            max_quota_retries=settings.PLANNER_MAX_429_RETRIES,
            quota_backoff_seconds=settings.PLANNER_429_BACKOFF_SECONDS,
            max_transient_retries=settings.PLANNER_MAX_TRANSIENT_RETRIES,
            transient_backoff_seconds=settings.PLANNER_TRANSIENT_BACKOFF_SECONDS,
            synthetic_values={
                "name": "Asha Test",
                "email": "asha.test@example.invalid",
            },
        )
        observations = [
            PlannerObservationV1(
                goal="Propose one safe keyboard action to focus the first link.",
                url="http://fixture/preflight",
                visible_text="Start journey",
                remaining_steps=calls,
            ),
            PlannerObservationV1(
                goal="Move keyboard focus from Back to Review appointment.",
                url="http://fixture/preflight/details",
                focused_element=ElementEvidenceV1(
                    fingerprint="a#.back",
                    role="link",
                    name="Back",
                    editable=False,
                ),
                visible_text="Back Review appointment",
                remaining_steps=calls,
            ),
        ]
        try:
            for index in range(calls):
                observation = observations[index % len(observations)]
                action = planner.propose_next_action(observation)
                if (
                    observation.focused_element is None
                    and action.action is not ActionKind.TAB
                ):
                    raise CommandError(
                        "GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE: "
                        "expected=tab when focus=null; "
                        f"actual={action.action.value}; attempted_calls={planner.calls}"
                    )
                if (
                    action.action is ActionKind.TYPE
                    and not (
                        observation.focused_element
                        and observation.focused_element.editable
                    )
                ):
                    raise CommandError(
                        "GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE: "
                        "type requires an editable focused element; "
                        f"actual_focus={observation.focused_element}; "
                        f"attempted_calls={planner.calls}"
                    )
                if (
                    index % len(observations) == 1
                    and action.action not in {ActionKind.TAB, ActionKind.SHIFT_TAB}
                ):
                    raise CommandError(
                        "GEMINI_PREFLIGHT_ACTION_INCOMPATIBLE: "
                        "the requested target is not the focused Back link; "
                        f"expected=tab_or_shift_tab; actual={action.action.value}; "
                        f"attempted_calls={planner.calls}"
                    )
                self.stdout.write(
                    f"Verified actions={index + 1}/{calls}; attempted_calls={planner.calls}"
                )
                self.stdout.flush()
        except PlannerError as error:
            provider_status = self._provider_status(error)
            provider_reason = self._provider_reason(error, api_key=api_key)
            status_detail = (
                f"; provider_status={provider_status}"
                if provider_status is not None
                else ""
            )
            reason_detail = (
                f"; provider_reason={provider_reason}" if provider_reason else ""
            )
            raise CommandError(
                f"GEMINI_PREFLIGHT_FAILED: {error.code}{status_detail}{reason_detail}; "
                f"attempted_calls={planner.calls}"
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                "GEMINI_PREFLIGHT_PASSED "
                f"model={selected_model} calls={calls} interval_seconds={interval:g}"
            )
        )

    @staticmethod
    def _provider_status(error: BaseException) -> int | None:
        """Return only a safe numeric provider status from a chained SDK error."""
        current: BaseException | None = error
        while current is not None:
            status = getattr(current, "code", None)
            if isinstance(status, int):
                return status
            current = current.__cause__
        return None

    @staticmethod
    def _provider_reason(error: BaseException, *, api_key: str) -> str:
        """Return a bounded, credential-redacted SDK message for preflight diagnosis."""
        current: BaseException | None = error
        while current is not None:
            message = getattr(current, "message", "")
            if isinstance(message, str) and message:
                redacted = message.replace(api_key, "[redacted]")
                redacted = re.sub(
                    r"(?i)(key|api_key)=([^&\s]+)", r"\1=[redacted]", redacted
                )
                return " ".join(redacted.split())[:240]
            current = current.__cause__
        return ""
