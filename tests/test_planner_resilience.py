from __future__ import annotations

import json
from email.message import Message
from io import BytesIO
from urllib.error import HTTPError

import pytest

from engine.contracts import ActionKind, PlannerObservationV1
from engine.groq import GroqActionClient
from engine.openrouter import OpenRouterActionClient
from engine.planner import (
    FixturePlanPlanner,
    GroqPlanner,
    OpenRouterPlanner,
    OpenRouterQuotaError,
    OpenRouterUnavailableError,
    PlannerError,
    ResilientPlanner,
    planner_from_config,
)

TAB = {"action": "tab", "purpose": "move focus"}


def observation() -> PlannerObservationV1:
    return PlannerObservationV1(
        goal="Open the accessibility article.",
        url="https://example.org/",
        visible_text="Search",
        remaining_steps=10,
    )


class ScriptedClient:
    """Raise or return each scripted item in turn."""

    def __init__(self, items: list[object]) -> None:
        self.items = list(items)
        self.calls = 0

    def generate_action(self, *, model: str, observation: PlannerObservationV1) -> object:
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def retryable_unavailable(message: str = "invalid completion") -> OpenRouterUnavailableError:
    error = OpenRouterUnavailableError(message)
    error.retryable = True
    return error


def fixture_fallback() -> FixturePlanPlanner:
    return FixturePlanPlanner({"kind": "fixture_plan.v1", "actions": [TAB]})


def test_one_bad_answer_is_retried_instead_of_falling_back() -> None:
    client = ScriptedClient([retryable_unavailable(), TAB])
    planner = ResilientPlanner(
        primary=OpenRouterPlanner(client=client, model="m", max_calls=10),
        fallback=fixture_fallback(),
    )

    action = planner.propose_next_action(observation())

    metadata = planner.runtime_metadata()
    assert action is not None and action.action == ActionKind.TAB
    assert metadata["fallback_used"] is False
    assert metadata["invalid_responses"] == 1
    assert metadata["calls"] == 2


def test_a_bad_key_falls_back_at_once_and_records_why() -> None:
    auth = OpenRouterUnavailableError("OpenRouter rejected the request (HTTP 401: No auth)")
    auth.code = "OPENROUTER_AUTH_FAILED"
    client = ScriptedClient([auth])
    planner = ResilientPlanner(
        primary=OpenRouterPlanner(client=client, model="m", max_calls=10),
        fallback=fixture_fallback(),
    )

    planner.propose_next_action(observation())

    metadata = planner.runtime_metadata()
    assert client.calls == 1
    assert metadata["fallback_reason"] == "OPENROUTER_AUTH_FAILED"
    assert "HTTP 401" in metadata["fallback_detail"]
    assert "OPENROUTER_AUTH_FAILED" in metadata["last_error"]


def test_quota_retry_waits_for_the_providers_retry_after() -> None:
    quota = OpenRouterQuotaError("rate limited")
    quota.retry_after = 42
    waits: list[float] = []
    planner = OpenRouterPlanner(
        client=ScriptedClient([quota, TAB]),
        model="m",
        max_calls=10,
        max_quota_retries=1,
        quota_backoff_seconds=5,
        sleep=waits.append,
    )

    planner.propose_next_action(observation())

    assert waits == [43]


def test_unexpected_groq_errors_are_labelled_as_groq() -> None:
    planner = GroqPlanner(client=ScriptedClient([RuntimeError("boom")]), model="m", max_calls=5)

    with pytest.raises(PlannerError) as raised:
        planner.propose_next_action(observation())

    assert raised.value.code == "GROQ_UNAVAILABLE"
    assert "boom" in str(raised.value)


def test_real_site_planner_without_fallback_stops_with_the_provider_reason() -> None:
    planner = planner_from_config(
        {"planner": {"kind": "groq.v1", "allow_no_fallback": True, "synthetic_values": {}}},
        groq_client=ScriptedClient([RuntimeError("down")]),
        groq_model="m",
        max_calls=5,
    )

    assert planner.propose_next_action(observation()) is None
    assert planner.stop_reason == "GROQ_UNAVAILABLE"
    assert planner.runtime_metadata()["planner_stop_reason"] == "GROQ_UNAVAILABLE"


def test_model_journeys_still_require_a_fallback_unless_marked_real_site() -> None:
    with pytest.raises(ValueError, match="MODEL_FALLBACK_PLAN_REQUIRED"):
        planner_from_config({"planner": {"kind": "groq.v1"}}, max_calls=5)


def _http_error(status: int, body: dict | None = None, headers: dict | None = None):
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value

    def opener(request, *, timeout):
        raise HTTPError(
            request.full_url, status, "error", message, BytesIO(json.dumps(body or {}).encode())
        )

    return opener


def _openrouter(opener) -> OpenRouterActionClient:
    return OpenRouterActionClient(
        api_key="sk-test-secret", timeout_seconds=5, min_interval_seconds=0, opener=opener
    )


def test_openrouter_404_is_retryable_and_keeps_the_provider_message() -> None:
    body = {"error": {"message": "No endpoints found that support the requested parameters"}}
    client = _openrouter(_http_error(404, body))

    with pytest.raises(OpenRouterUnavailableError) as raised:
        client.generate_action(model="openrouter/free", observation=observation())

    assert raised.value.retryable is True
    assert "No endpoints found" in str(raised.value)


def test_openrouter_401_is_a_fatal_auth_error_without_the_key() -> None:
    body = {"error": {"message": "Invalid key sk-test-secret"}}
    client = _openrouter(_http_error(401, body))

    with pytest.raises(OpenRouterUnavailableError) as raised:
        client.generate_action(model="m", observation=observation())

    assert raised.value.code == "OPENROUTER_AUTH_FAILED"
    assert raised.value.retryable is False
    assert "sk-test-secret" not in str(raised.value)


def test_openrouter_429_reads_retry_after() -> None:
    client = _openrouter(_http_error(429, headers={"Retry-After": "17"}))

    with pytest.raises(OpenRouterQuotaError) as raised:
        client.generate_action(model="m", observation=observation())

    assert raised.value.retry_after == 17


def test_truncated_completion_explains_itself_and_is_retryable() -> None:
    class Truncated:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "model": "some/reasoner:free",
                    "choices": [{"finish_reason": "length", "message": {"content": None}}],
                }
            ).encode()

    client = _openrouter(lambda request, *, timeout: Truncated())

    with pytest.raises(OpenRouterUnavailableError) as raised:
        client.generate_action(model="openrouter/free", observation=observation())

    assert raised.value.retryable is True
    assert "ran out of output tokens" in str(raised.value)
    assert "some/reasoner:free" in str(raised.value)


def test_groq_400_json_failure_is_retryable_and_404_is_model_not_found() -> None:
    def groq(status: int) -> GroqActionClient:
        return GroqActionClient(
            api_key="gsk-test",
            timeout_seconds=5,
            min_interval_seconds=0,
            opener=_http_error(status, {"error": {"message": "json_validate_failed"}}),
        )

    with pytest.raises(PlannerError) as bad_json:
        groq(400).generate_action(model="m", observation=observation())
    with pytest.raises(PlannerError) as missing:
        groq(404).generate_action(model="m", observation=observation())

    assert bad_json.value.retryable is True
    assert missing.value.code == "GROQ_MODEL_NOT_FOUND"
    assert missing.value.retryable is False


def test_groq_429_without_header_reads_the_wait_from_the_message() -> None:
    body = {"error": {"message": "Rate limit reached on TPM. Please try again in 9.3375s."}}
    client = GroqActionClient(
        api_key="gsk-test",
        timeout_seconds=5,
        min_interval_seconds=0,
        opener=_http_error(429, body),
    )

    with pytest.raises(PlannerError) as raised:
        client.generate_action(model="m", observation=observation())

    assert raised.value.retry_after == pytest.approx(9.3375)


def test_retry_after_hint_allows_a_few_patient_quota_retries() -> None:
    def limited() -> OpenRouterQuotaError:
        error = OpenRouterQuotaError("tokens per minute")
        error.retry_after = 2
        return error

    waits: list[float] = []
    planner = OpenRouterPlanner(
        client=ScriptedClient([limited(), limited(), limited(), TAB]),
        model="m",
        max_calls=10,
        max_quota_retries=1,
        sleep=waits.append,
    )

    action = planner.propose_next_action(observation())

    assert action.action == ActionKind.TAB
    assert waits == [3, 3, 3]
