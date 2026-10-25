from __future__ import annotations

from typing import Any

import pytest

from engine.contracts import (
    ActionKind,
    ActionResultV1,
    PlannerObservationV1,
    PolicyDecisionV1,
    ProposedActionV1,
)
from engine.planner import (
    FixturePlanPlanner,
    GeminiPlanner,
    GeminiQuotaError,
    GeminiTimeoutError,
    GeminiTransientError,
    ResilientPlanner,
    planner_from_config,
)


class StubGeminiClient:
    def __init__(self, responses: list[object]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    def generate_action(self, *, model: str, observation: PlannerObservationV1) -> object:
        self.calls += 1
        return next(self.responses)


def observation() -> PlannerObservationV1:
    return PlannerObservationV1(
        goal="Complete the appointment journey using keyboard actions.",
        url="http://fixture/accessible/index.html",
        visible_text="Choose a service",
        remaining_steps=24,
    )


def fallback_planner() -> FixturePlanPlanner:
    return FixturePlanPlanner(
        {
            "kind": "fixture_plan.v1",
            "actions": [
                {"action": "tab", "purpose": "focus the journey entry link"},
                {"action": "enter", "purpose": "open the journey"},
            ],
        }
    )


def test_gemini_planner_returns_only_a_typed_keyboard_action() -> None:
    client = StubGeminiClient(
        [{"action": "tab", "target_hint": "Choose a service", "purpose": "focus entry"}]
    )
    planner = GeminiPlanner(client=client, model="models/account-verified", max_calls=4)

    action = planner.propose_next_action(observation())

    assert action == ProposedActionV1(
        action=ActionKind.TAB,
        target_hint="Choose a service",
        purpose="focus entry",
    )
    assert planner.runtime_metadata()["model"] == "models/account-verified"
    assert planner.runtime_metadata()["calls"] == 1


@pytest.mark.parametrize(
    "response",
    [
        {"action": "click", "purpose": "bypass keyboard navigation"},
        {"action": "tab", "script": "document.querySelector('button').click()"},
        "not-json",
    ],
)
def test_malformed_or_unsafe_gemini_output_uses_labeled_fixture_fallback(
    response: object,
) -> None:
    planner = ResilientPlanner(
        primary=GeminiPlanner(
            client=StubGeminiClient([response]),
            model="models/account-verified",
            max_calls=4,
        ),
        fallback=fallback_planner(),
    )

    action = planner.propose_next_action(observation())

    assert action is not None
    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["fallback_used"] is True
    assert planner.runtime_metadata()["fallback_reason"] == "MALFORMED_MODEL_OUTPUT"


def test_quota_failure_uses_labeled_fixture_fallback() -> None:
    class QuotaClient:
        def generate_action(self, **_: Any) -> object:
            raise GeminiQuotaError("quota unavailable")

    planner = ResilientPlanner(
        primary=GeminiPlanner(
            client=QuotaClient(),
            model="models/account-verified",
            max_calls=4,
        ),
        fallback=fallback_planner(),
    )

    action = planner.propose_next_action(observation())

    assert action is not None
    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["fallback_reason"] == "GEMINI_QUOTA_FAILURE"


def test_timeout_uses_labeled_fixture_fallback() -> None:
    class TimeoutClient:
        def generate_action(self, **_: Any) -> object:
            raise TimeoutError("request exceeded its deadline")

    planner = ResilientPlanner(
        primary=GeminiPlanner(
            client=TimeoutClient(),
            model="models/account-verified",
            max_calls=4,
        ),
        fallback=fallback_planner(),
    )

    action = planner.propose_next_action(observation())

    assert action is not None
    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["fallback_reason"] == "GEMINI_TIMEOUT"
    assert planner.consume_reset_request() is True
    assert planner.consume_reset_request() is False
    assert planner.runtime_metadata()["fallback_restarted"] is True


def test_transient_provider_failure_retries_once_before_fallback() -> None:
    class TransientThenSafeClient:
        def __init__(self) -> None:
            self.calls = 0

        def generate_action(self, **_: Any) -> object:
            self.calls += 1
            if self.calls == 1:
                raise GeminiTransientError("temporary provider failure")
            return {"action": "tab", "purpose": "continue safely"}

    client = TransientThenSafeClient()
    planner = GeminiPlanner(
        client=client,
        model="models/account-verified",
        max_calls=4,
        max_transient_retries=1,
        transient_backoff_seconds=0,
    )

    action = planner.propose_next_action(observation())

    assert action.action == ActionKind.TAB
    assert client.calls == 2
    assert planner.runtime_metadata()["calls"] == 2
    assert planner.runtime_metadata()["successful_proposals"] == 1
    assert planner.runtime_metadata()["transient_failures"] == 1
    assert planner.runtime_metadata()["quota_failures"] == 0


def test_provider_timeout_retries_within_transient_budget() -> None:
    class TimeoutThenSafeClient(StubGeminiClient):
        def generate_action(self, *, model: str, observation: PlannerObservationV1) -> object:
            response = super().generate_action(model=model, observation=observation)
            if isinstance(response, Exception):
                raise response
            return response

    planner = GeminiPlanner(
        client=TimeoutThenSafeClient(
            [
                GeminiTimeoutError("provider deadline expired"),
                {"action": "tab", "purpose": "continue after timeout"},
            ]
        ),
        model="models/account-verified",
        max_calls=4,
        max_transient_retries=1,
        transient_backoff_seconds=0,
    )

    action = planner.propose_next_action(observation())

    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["calls"] == 2
    assert planner.runtime_metadata()["successful_proposals"] == 1
    assert planner.runtime_metadata()["transient_failures"] == 1


def test_policy_rejection_keeps_gemini_in_control_for_bounded_replan() -> None:
    planner = ResilientPlanner(
        primary=GeminiPlanner(
            client=StubGeminiClient(
                [
                    {"action": "type", "value": "unsafe", "purpose": "type into body"},
                    {"action": "shift_tab", "purpose": "move to the intended control"},
                ]
            ),
            model="models/account-verified",
            max_calls=4,
        ),
        fallback=fallback_planner(),
    )
    current = observation()
    proposed = planner.propose_next_action(current)
    assert proposed is not None

    planner.record_outcome(
        current,
        proposed,
        PolicyDecisionV1(outcome="rejected", code="TYPE_TARGET_NOT_EDITABLE"),
        ActionResultV1(
            status="rejected",
            meaningful_progress=False,
            error_code="TYPE_TARGET_NOT_EDITABLE",
        ),
    )
    replacement = planner.propose_next_action(current)

    assert replacement is not None
    assert replacement.action == ActionKind.SHIFT_TAB
    assert planner.runtime_metadata()["fallback_used"] is False
    assert planner.runtime_metadata()["policy_rejections"] == 1
    assert planner.consume_reset_request() is False


def test_gemini_call_limit_uses_fallback_instead_of_unbounded_calls() -> None:
    client = StubGeminiClient(
        [{"action": "tab", "purpose": "first"}, {"action": "enter", "purpose": "second"}]
    )
    planner = ResilientPlanner(
        primary=GeminiPlanner(
            client=client,
            model="models/account-verified",
            max_calls=1,
        ),
        fallback=fallback_planner(),
    )
    first = planner.propose_next_action(observation())
    assert first is not None
    planner.record_outcome(
        observation(),
        first,
        PolicyDecisionV1(outcome="approved", code="ACTION_ALLOWED"),
        ActionResultV1(status="effect_observed", meaningful_progress=True),
    )

    second = planner.propose_next_action(observation())

    assert second is not None
    assert client.calls == 1
    assert planner.runtime_metadata()["fallback_reason"] == "PLANNER_CALL_LIMIT_EXCEEDED"


def test_planner_observation_enforces_privacy_and_size_limits() -> None:
    with pytest.raises(ValueError):
        PlannerObservationV1(
            goal="bounded goal",
            url="http://fixture/accessible/index.html",
            visible_text="x" * 4001,
            remaining_steps=1,
        )


def test_gemini_configuration_without_verified_runtime_uses_visible_contingency() -> None:
    planner = planner_from_config(
        {
            "planner": {
                "kind": "gemini.v1",
                "fallback": {
                    "kind": "fixture_plan.v1",
                    "actions": [{"action": "tab", "purpose": "safe contingency"}],
                },
            }
        },
        gemini_client=None,
        gemini_model="",
        max_calls=4,
    )

    action = planner.propose_next_action(observation())

    assert action is not None
    assert action.action == ActionKind.TAB
    assert planner.runtime_metadata()["fallback_used"] is True
    assert planner.runtime_metadata()["fallback_reason"] == "GEMINI_PREFLIGHT_REQUIRED"


def test_openrouter_configuration_persists_distinct_provider_metadata() -> None:
    planner = planner_from_config(
        {
            "planner": {
                "kind": "openrouter.v1",
                "fallback": {
                    "kind": "fixture_plan.v1",
                    "actions": [{"action": "tab", "purpose": "safe contingency"}],
                },
            }
        },
        openrouter_client=StubGeminiClient(
            [{"action": "tab", "purpose": "focus the entry link"}]
        ),
        openrouter_model="openai/gpt-4.1-mini",
        max_calls=4,
    )

    action = planner.propose_next_action(observation())

    assert action is not None
    metadata = planner.runtime_metadata()
    assert metadata["kind"] == "openrouter.v1"
    assert metadata["provider"] == "openrouter"
    assert metadata["fallback_used"] is False

