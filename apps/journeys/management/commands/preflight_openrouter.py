from __future__ import annotations

import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from engine.contracts import ActionKind, ElementEvidenceV1, PlannerObservationV1
from engine.openrouter import OpenRouterActionClient
from engine.planner import OpenRouterPlanner, PlannerError


class Command(BaseCommand):
    help = "Verify a configured OpenRouter model can return bounded structured keyboard actions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--model", default="", help="Exact OpenRouter model ID to verify.")
        parser.add_argument("--calls", type=int, default=3)
        parser.add_argument("--interval", type=float, default=None)

    def handle(self, *args, **options) -> None:
        del args
        if not settings.OPENROUTER_API_KEY:
            raise CommandError("OPENROUTER_API_KEY_NOT_CONFIGURED")
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
        model = options["model"] or settings.OPENROUTER_MODEL
        if not model:
            raise CommandError("OPENROUTER_MODEL_NOT_SELECTED")

        planner = OpenRouterPlanner(
            client=OpenRouterActionClient(
                api_key=settings.OPENROUTER_API_KEY,
                timeout_seconds=settings.PLANNER_CALL_TIMEOUT_SECONDS,
                min_interval_seconds=interval,
            ),
            model=model,
            max_calls=calls
            * (1 + settings.PLANNER_MAX_429_RETRIES + settings.PLANNER_MAX_TRANSIENT_RETRIES),
            max_quota_retries=settings.PLANNER_MAX_429_RETRIES,
            quota_backoff_seconds=settings.PLANNER_429_BACKOFF_SECONDS,
            max_transient_retries=settings.PLANNER_MAX_TRANSIENT_RETRIES,
            transient_backoff_seconds=settings.PLANNER_TRANSIENT_BACKOFF_SECONDS,
            synthetic_values={"name": "Asha Test", "email": "asha.test@example.invalid"},
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
                self._assert_semantic_action(index, observation, action, planner.calls)
                self.stdout.write(
                    f"Verified actions={index + 1}/{calls}; attempted_calls={planner.calls}"
                )
                self.stdout.flush()
        except PlannerError as error:
            provider_status = self._provider_status(error)
            status_detail = f"; provider_status={provider_status}" if provider_status else ""
            reason = self._provider_reason(error, api_key=settings.OPENROUTER_API_KEY)
            reason_detail = f"; provider_reason={reason}" if reason else ""
            raise CommandError(
                "OPENROUTER_PREFLIGHT_FAILED: "
                f"{error.code}{status_detail}{reason_detail}; attempted_calls={planner.calls}"
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                "OPENROUTER_PREFLIGHT_PASSED "
                f"model={model} calls={calls} interval_seconds={interval:g}"
            )
        )

    @staticmethod
    def _assert_semantic_action(
        index: int,
        observation: PlannerObservationV1,
        action,
        attempted_calls: int,
    ) -> None:
        if observation.focused_element is None and action.action is not ActionKind.TAB:
            raise CommandError(
                "OPENROUTER_PREFLIGHT_ACTION_INCOMPATIBLE: expected=tab when focus=null; "
                f"actual={action.action.value}; attempted_calls={attempted_calls}"
            )
        if action.action is ActionKind.TYPE and not (
            observation.focused_element and observation.focused_element.editable
        ):
            raise CommandError(
                "OPENROUTER_PREFLIGHT_ACTION_INCOMPATIBLE: type requires an editable focused "
                f"element; attempted_calls={attempted_calls}"
            )
        if index % 2 == 1 and action.action not in {ActionKind.TAB, ActionKind.SHIFT_TAB}:
            raise CommandError(
                "OPENROUTER_PREFLIGHT_ACTION_INCOMPATIBLE: expected=tab_or_shift_tab; "
                f"actual={action.action.value}; attempted_calls={attempted_calls}"
            )

    @staticmethod
    def _provider_status(error: BaseException) -> int | None:
        """Expose only a numeric upstream status; credentials and payloads remain private."""
        current: BaseException | None = error
        while current is not None:
            status = getattr(current, "code", None)
            if isinstance(status, int):
                return status
            current = current.__cause__
        return None

    @staticmethod
    def _provider_reason(error: BaseException, *, api_key: str) -> str:
        """Bound and redact provider detail so diagnostics never expose a key."""
        current: BaseException | None = error
        while current is not None:
            message = str(current)
            if message:
                redacted = message.replace(api_key, "[redacted]")
                redacted = re.sub(r"(?i)(key|api_key)=([^&\s]+)", r"\1=[redacted]", redacted)
                return " ".join(redacted.split())[:280]
            current = current.__cause__
        return ""
