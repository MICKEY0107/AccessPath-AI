"""Planner interfaces and configuration-driven adapters.

The executor never contains a site-specific path. A journey selects a planner
through persisted configuration. The fixture-plan adapter is deliberately
limited to controlled test targets; Gemini can later be selected without
changing the execution or evidence interfaces.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Any, Protocol

from pydantic import ValidationError

from .contracts import (
    ActionKind,
    ActionResultV1,
    PlannerObservationV1,
    PolicyDecisionV1,
    ProposedActionV1,
)


class PlannerError(RuntimeError):
    code = "PLANNER_ERROR"
    # A retryable error is a one-off bad answer (empty, truncated, unroutable) that a
    # fresh call can fix; a non-retryable one (bad key, unknown model) cannot.
    retryable = False
    # Seconds the provider asked us to wait (HTTP Retry-After), when it said so.
    retry_after: float | None = None


class GeminiTimeoutError(PlannerError):
    code = "GEMINI_TIMEOUT"


class GeminiQuotaError(PlannerError):
    code = "GEMINI_QUOTA_FAILURE"


class GeminiUnavailableError(PlannerError):
    code = "GEMINI_UNAVAILABLE"


class GeminiTransientError(PlannerError):
    code = "GEMINI_TRANSIENT_FAILURE"


class OpenRouterTimeoutError(GeminiTimeoutError):
    code = "OPENROUTER_TIMEOUT"


class OpenRouterQuotaError(GeminiQuotaError):
    code = "OPENROUTER_QUOTA_FAILURE"


class OpenRouterUnavailableError(GeminiUnavailableError):
    code = "OPENROUTER_UNAVAILABLE"


class OpenRouterTransientError(GeminiTransientError):
    code = "OPENROUTER_TRANSIENT_FAILURE"


class GroqTimeoutError(GeminiTimeoutError):
    code = "GROQ_TIMEOUT"


class GroqQuotaError(GeminiQuotaError):
    code = "GROQ_QUOTA_FAILURE"


class GroqUnavailableError(GeminiUnavailableError):
    code = "GROQ_UNAVAILABLE"


class GroqTransientError(GeminiTransientError):
    code = "GROQ_TRANSIENT_FAILURE"


class MalformedModelOutputError(PlannerError):
    code = "MALFORMED_MODEL_OUTPUT"
    retryable = True


class PlannerCallLimitError(PlannerError):
    code = "PLANNER_CALL_LIMIT_EXCEEDED"


class GeminiActionClient(Protocol):
    def generate_action(self, *, model: str, observation: PlannerObservationV1) -> object: ...


class Planner(Protocol):
    def propose_next_action(
        self, observation: PlannerObservationV1
    ) -> ProposedActionV1 | None: ...

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None: ...

    def runtime_metadata(self) -> dict[str, object]: ...


class FixturePlanPlanner:
    """Reads a declared keyboard plan from a versioned journey configuration."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._iterator = self._build_actions()

    def _build_actions(self) -> Iterator[ProposedActionV1]:
        for item in self._config.get("actions", []):
            values = self._config.get("synthetic_values", {})
            value = item.get("value")
            if isinstance(value, str):
                value = value.format(**values)
            yield ProposedActionV1(
                action=ActionKind(item["action"]),
                value=value,
                target_hint=item.get("target_hint", ""),
                purpose=item.get("purpose", ""),
            )

    def actions(self) -> Iterator[ProposedActionV1]:
        """Compatibility iterator used by deterministic engine tests."""
        yield from self._build_actions()

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1 | None:
        del observation
        return next(self._iterator, None)

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None:
        del observation, action, decision, result

    def runtime_metadata(self) -> dict[str, object]:
        return {"kind": "fixture_plan.v1", "fallback_used": False}


class GeminiPlanner:
    """Request one provider-structured, server-validated keyboard action per turn."""

    def __init__(
        self,
        *,
        client: GeminiActionClient,
        model: str,
        max_calls: int,
        max_quota_retries: int = 0,
        quota_backoff_seconds: float = 0,
        max_transient_retries: int = 0,
        transient_backoff_seconds: float = 0,
        max_invalid_retries: int = 2,
        synthetic_values: dict[str, str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model:
            raise ValueError("GEMINI_MODEL_NOT_VERIFIED")
        if max_calls < 1:
            raise ValueError("PLANNER_MAX_CALLS_MUST_BE_POSITIVE")
        self.client = client
        self.model = model
        self.max_calls = max_calls
        self.max_quota_retries = max_quota_retries
        self.quota_backoff_seconds = quota_backoff_seconds
        self.max_transient_retries = max_transient_retries
        self.transient_backoff_seconds = transient_backoff_seconds
        self.max_invalid_retries = max_invalid_retries
        self.synthetic_values = synthetic_values or {}
        self.sleep = sleep
        self.calls = 0
        self.successful_proposals = 0
        self.quota_failures = 0
        self.transient_failures = 0
        self.invalid_responses = 0
        self.last_error = ""

    # Provider-specific error family, so a Groq failure is never labelled as Gemini.
    provider_label = "Gemini"
    unavailable_error: type[PlannerError] = GeminiUnavailableError
    timeout_error: type[PlannerError] = GeminiTimeoutError
    quota_error: type[PlannerError] = GeminiQuotaError
    # Cap on a provider-requested Retry-After wait, so one run cannot stall for long.
    max_retry_after_seconds = 120.0

    def _note_error(self, error: PlannerError) -> None:
        self.last_error = f"{error.code}: {error}"[:300]

    # A provider that says exactly when to retry (per-minute token limits) gets a few
    # more patient retries than the configured blind backoff allows.
    min_quota_retries_with_retry_after = 3

    def _quota_wait_seconds(self, error: PlannerError) -> float:
        if error.retry_after is not None:
            return min(error.retry_after + 1, self.max_retry_after_seconds)
        return self.quota_backoff_seconds

    def _quota_retry_budget(self, error: PlannerError) -> int:
        if error.retry_after is not None and error.retry_after < self.max_retry_after_seconds:
            return max(self.max_quota_retries, self.min_quota_retries_with_retry_after)
        return self.max_quota_retries

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        if self.calls >= self.max_calls:
            raise PlannerCallLimitError(f"{self.provider_label} planner call budget exhausted")

        bounded_observation = PlannerObservationV1.model_validate(
            {
                **observation.model_dump(mode="json"),
                "permitted_inputs": self.synthetic_values,
            }
        )
        quota_attempts = 0
        transient_attempts = 0
        invalid_attempts = 0
        while True:
            self.calls += 1
            try:
                action = self._request_action(bounded_observation)
                break
            except GeminiQuotaError as error:
                self.quota_failures += 1
                self._note_error(error)
                if (
                    quota_attempts >= self._quota_retry_budget(error)
                    or self.calls >= self.max_calls
                ):
                    raise
                quota_attempts += 1
                self.sleep(self._quota_wait_seconds(error))
            except (GeminiTransientError, GeminiTimeoutError) as error:
                self.transient_failures += 1
                self._note_error(error)
                if (
                    transient_attempts >= self.max_transient_retries
                    or self.calls >= self.max_calls
                ):
                    raise
                transient_attempts += 1
                self.sleep(self.transient_backoff_seconds)
            except PlannerError as error:
                self._note_error(error)
                if not error.retryable:
                    raise
                self.invalid_responses += 1
                if invalid_attempts >= self.max_invalid_retries or self.calls >= self.max_calls:
                    raise
                # The process-wide pacer already spaces the next call out.
                invalid_attempts += 1
        self.successful_proposals += 1
        return action

    def _request_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        """Make one provider call and turn every failure into a labelled PlannerError."""
        label = self.provider_label
        try:
            raw_action = self.client.generate_action(model=self.model, observation=observation)
        except PlannerError:
            raise
        except TimeoutError as error:
            raise self.timeout_error(f"{label} request timed out") from error
        except Exception as error:
            if getattr(error, "code", None) == 429:
                raise self.quota_error(f"{label} quota unavailable") from error
            if "timeout" in type(error).__name__.lower():
                raise self.timeout_error(f"{label} request timed out") from error
            message = " ".join(str(error).split())[:200]
            raise self.unavailable_error(
                f"{label} request failed: {type(error).__name__}: {message}"
            ) from error
        try:
            return ProposedActionV1.model_validate(raw_action)
        except (ValidationError, TypeError, ValueError) as error:
            raise MalformedModelOutputError(
                f"{label} returned an action that does not match the schema"
            ) from error

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None:
        del observation, action, decision, result

    def runtime_metadata(self) -> dict[str, object]:
        return {
            "kind": "gemini.v1",
            "provider": "gemini",
            "provider_label": "Gemini",
            "model": self.model,
            "calls": self.calls,
            "successful_proposals": self.successful_proposals,
            "quota_failures": self.quota_failures,
            "transient_failures": self.transient_failures,
            "invalid_responses": self.invalid_responses,
            "last_error": self.last_error,
            "fallback_used": False,
        }


class OpenRouterPlanner(GeminiPlanner):
    """Reuse bounded structured-action planning with OpenRouter-specific evidence labels."""

    provider_label = "OpenRouter"
    unavailable_error = OpenRouterUnavailableError
    timeout_error = OpenRouterTimeoutError
    quota_error = OpenRouterQuotaError

    def __init__(self, **kwargs: Any) -> None:
        if not kwargs.get("model"):
            raise ValueError("OPENROUTER_MODEL_NOT_CONFIGURED")
        super().__init__(**kwargs)

    def runtime_metadata(self) -> dict[str, object]:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "kind": "openrouter.v1",
                "provider": "openrouter",
                "provider_label": "OpenRouter",
            }
        )
        resolved_model = getattr(self.client, "last_response_model", "")
        if isinstance(resolved_model, str) and resolved_model:
            metadata["resolved_model"] = resolved_model
        return metadata


class ResilientPlanner:
    """Use an explicitly labeled deterministic contingency after a safe planner stop.

    Journeys on real sites have no scripted contingency (``fallback`` is None). There a
    provider failure ends the run with the provider's reason instead of a replay.
    """

    def __init__(self, *, primary: Planner, fallback: Planner | None) -> None:
        self.primary = primary
        self.fallback = fallback
        self._fallback_used = False
        self._fallback_reason = ""
        self._fallback_detail = ""
        self.stop_reason = ""
        self.stop_detail = ""
        self._reset_requested = False
        self._fallback_restarted = False
        self._policy_rejections = 0

    def _activate_fallback(self, reason: str) -> None:
        if self._fallback_used:
            return
        self._fallback_used = True
        self._fallback_reason = reason
        self._reset_requested = True

    def consume_reset_request(self) -> bool:
        """Request one executor-controlled restart at the approved journey URL."""
        if not self._reset_requested:
            return False
        self._reset_requested = False
        self._fallback_restarted = True
        return True

    def propose_next_action(
        self, observation: PlannerObservationV1
    ) -> ProposedActionV1 | None:
        if self.stop_reason:
            return None
        if self._fallback_used and self.fallback is not None:
            return self.fallback.propose_next_action(observation)
        try:
            return self.primary.propose_next_action(observation)
        except PlannerError as error:
            detail = " ".join(str(error).split())[:300]
            if self.fallback is None:
                self.stop_reason = error.code
                self.stop_detail = detail
                return None
            self._activate_fallback(error.code)
            self._fallback_detail = detail
            return self.fallback.propose_next_action(observation)

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None:
        if self._fallback_used and self.fallback is not None:
            self.fallback.record_outcome(observation, action, decision, result)
            return

        self.primary.record_outcome(observation, action, decision, result)
        if decision.outcome == "rejected":
            self._policy_rejections += 1

    def runtime_metadata(self) -> dict[str, object]:
        metadata = self.primary.runtime_metadata()
        metadata.update(
            {
                "fallback_used": self._fallback_used,
                "fallback_reason": self._fallback_reason,
                "fallback_detail": self._fallback_detail,
                "fallback_kind": (
                    self.fallback.runtime_metadata().get("kind") if self.fallback else None
                ),
                "planner_stop_reason": self.stop_reason,
                "fallback_restarted": self._fallback_restarted,
                "policy_rejections": self._policy_rejections,
            }
        )
        return metadata


class UnavailableGeminiPlanner:
    """Represent an unverified provider runtime so fallback is explicit and auditable."""

    def __init__(self, *, model: str, reason: str) -> None:
        self.model = model
        self.reason = reason

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        del observation
        error = GeminiUnavailableError("Gemini runtime has not passed preflight")
        error.code = self.reason
        raise error

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None:
        del observation, action, decision, result

    def runtime_metadata(self) -> dict[str, object]:
        return {
            "kind": "gemini.v1",
            "provider": "gemini",
            "provider_label": "Gemini",
            "model": self.model,
            "calls": 0,
            "fallback_used": False,
        }


class UnavailableOpenRouterPlanner(UnavailableGeminiPlanner):
    """Represent an unavailable OpenRouter runtime without hiding contingency use."""

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        del observation
        error = OpenRouterUnavailableError("OpenRouter runtime has not passed preflight")
        error.code = self.reason
        raise error

    def runtime_metadata(self) -> dict[str, object]:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "kind": "openrouter.v1",
                "provider": "openrouter",
                "provider_label": "OpenRouter",
            }
        )
        return metadata


class GroqPlanner(OpenRouterPlanner):
    """Groq-specific metadata labels on top of identical structured-action logic."""

    provider_label = "Groq"
    unavailable_error = GroqUnavailableError
    timeout_error = GroqTimeoutError
    quota_error = GroqQuotaError

    def runtime_metadata(self) -> dict[str, object]:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "kind": "groq.v1",
                "provider": "groq",
                "provider_label": "Groq",
            }
        )
        resolved_model = getattr(self.client, "last_response_model", "")
        if isinstance(resolved_model, str) and resolved_model:
            metadata["resolved_model"] = resolved_model
        return metadata


class UnavailableGroqPlanner(UnavailableGeminiPlanner):
    """Represent an unavailable Groq runtime without hiding contingency use."""

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        del observation
        error = GroqUnavailableError("Groq runtime has not passed preflight")
        error.code = self.reason
        raise error

    def runtime_metadata(self) -> dict[str, object]:
        metadata = super().runtime_metadata()
        metadata.update(
            {
                "kind": "groq.v1",
                "provider": "groq",
                "provider_label": "Groq",
            }
        )
        return metadata


def planner_from_config(
    config: dict[str, Any],
    *,
    gemini_client: GeminiActionClient | None = None,
    gemini_model: str = "",
    openrouter_client: GeminiActionClient | None = None,
    openrouter_model: str = "",
    groq_client: GeminiActionClient | None = None,
    groq_model: str = "",
    max_calls: int = 30,
    max_quota_retries: int = 1,
    quota_backoff_seconds: float = 30,
    max_transient_retries: int = 2,
    transient_backoff_seconds: float = 15,
    max_invalid_retries: int = 2,
) -> Planner:
    planner = config.get("planner", {})
    kind = planner.get("kind")
    if kind == "fixture_plan.v1":
        return FixturePlanPlanner(planner)
    if kind in {"gemini.v1", "openrouter.v1", "groq.v1"}:
        fallback_config = planner.get("fallback")
        fallback: Planner | None = None
        if fallback_config is None and planner.get("allow_no_fallback"):
            # Real-site journeys: values the model may type live on the planner itself.
            fallback_config = {"synthetic_values": planner.get("synthetic_values", {})}
        elif (
            not isinstance(fallback_config, dict)
            or fallback_config.get("kind") != "fixture_plan.v1"
        ):
            raise ValueError("MODEL_FALLBACK_PLAN_REQUIRED")
        else:
            fallback = FixturePlanPlanner(fallback_config)
        if kind == "openrouter.v1":
            if openrouter_client is None or not openrouter_model:
                primary = UnavailableOpenRouterPlanner(
                    model=openrouter_model,
                    reason="OPENROUTER_PREFLIGHT_REQUIRED",
                )
            else:
                primary = OpenRouterPlanner(
                    client=openrouter_client,
                    model=openrouter_model,
                    max_calls=max_calls,
                    max_quota_retries=max_quota_retries,
                    quota_backoff_seconds=quota_backoff_seconds,
                    max_transient_retries=max_transient_retries,
                    transient_backoff_seconds=transient_backoff_seconds,
                    max_invalid_retries=max_invalid_retries,
                    synthetic_values=fallback_config.get("synthetic_values", {}),
                )
        elif kind == "groq.v1":
            if groq_client is None or not groq_model:
                primary = UnavailableGroqPlanner(
                    model=groq_model,
                    reason="GROQ_PREFLIGHT_REQUIRED",
                )
            else:
                primary = GroqPlanner(
                    client=groq_client,
                    model=groq_model,
                    max_calls=max_calls,
                    max_quota_retries=max_quota_retries,
                    quota_backoff_seconds=quota_backoff_seconds,
                    max_transient_retries=max_transient_retries,
                    transient_backoff_seconds=transient_backoff_seconds,
                    max_invalid_retries=max_invalid_retries,
                    synthetic_values=fallback_config.get("synthetic_values", {}),
                )
        else:
            if gemini_client is None or not gemini_model:
                primary = UnavailableGeminiPlanner(
                    model=gemini_model,
                    reason="GEMINI_PREFLIGHT_REQUIRED",
                )
            else:
                primary = GeminiPlanner(
                    client=gemini_client,
                    model=gemini_model,
                    max_calls=max_calls,
                    max_quota_retries=max_quota_retries,
                    quota_backoff_seconds=quota_backoff_seconds,
                    max_transient_retries=max_transient_retries,
                    transient_backoff_seconds=transient_backoff_seconds,
                    max_invalid_retries=max_invalid_retries,
                    synthetic_values=fallback_config.get("synthetic_values", {}),
                )
        return ResilientPlanner(primary=primary, fallback=fallback)
    raise ValueError(f"Unsupported planner kind: {kind!r}")
