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
        self.synthetic_values = synthetic_values or {}
        self.sleep = sleep
        self.calls = 0
        self.successful_proposals = 0
        self.quota_failures = 0
        self.transient_failures = 0

    def propose_next_action(self, observation: PlannerObservationV1) -> ProposedActionV1:
        if self.calls >= self.max_calls:
            raise PlannerCallLimitError("Gemini planner call budget exhausted")

        attempts = 0
        transient_attempts = 0
        while True:
            self.calls += 1
            try:
                bounded_observation = PlannerObservationV1.model_validate(
                    {
                        **observation.model_dump(mode="json"),
                        "permitted_inputs": self.synthetic_values,
                    }
                )
                raw_action = self.client.generate_action(
                    model=self.model,
                    observation=bounded_observation,
                )
                break
            except GeminiQuotaError:
                self.quota_failures += 1
                if attempts >= self.max_quota_retries or self.calls >= self.max_calls:
                    raise
                attempts += 1
                self.sleep(self.quota_backoff_seconds)
            except (GeminiTransientError, GeminiTimeoutError):
                self.transient_failures += 1
                if (
                    transient_attempts >= self.max_transient_retries
                    or self.calls >= self.max_calls
                ):
                    raise
                transient_attempts += 1
                self.sleep(self.transient_backoff_seconds)
            except PlannerError:
                raise
            except TimeoutError as error:
                raise GeminiTimeoutError("Gemini request timed out") from error
            except Exception as error:
                if getattr(error, "code", None) == 429:
                    raise GeminiQuotaError("Gemini quota unavailable") from error
                if "timeout" in type(error).__name__.lower():
                    raise GeminiTimeoutError("Gemini request timed out") from error
                raise GeminiUnavailableError("Gemini request failed") from error

        try:
            action = ProposedActionV1.model_validate(raw_action)
        except (ValidationError, TypeError, ValueError) as error:
            raise MalformedModelOutputError("Gemini returned an invalid action") from error
        self.successful_proposals += 1
        return action

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
            "fallback_used": False,
        }


class OpenRouterPlanner(GeminiPlanner):
    """Reuse bounded structured-action planning with OpenRouter-specific evidence labels."""

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
    """Use an explicitly labeled deterministic contingency after a safe planner stop."""

    def __init__(self, *, primary: Planner, fallback: Planner) -> None:
        self.primary = primary
        self.fallback = fallback
        self._fallback_used = False
        self._fallback_reason = ""
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
        if self._fallback_used:
            return self.fallback.propose_next_action(observation)
        try:
            return self.primary.propose_next_action(observation)
        except PlannerError as error:
            self._activate_fallback(error.code)
            return self.fallback.propose_next_action(observation)

    def record_outcome(
        self,
        observation: PlannerObservationV1,
        action: ProposedActionV1,
        decision: PolicyDecisionV1,
        result: ActionResultV1,
    ) -> None:
        if self._fallback_used:
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
                "fallback_kind": self.fallback.runtime_metadata().get("kind"),
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
) -> Planner:
    planner = config.get("planner", {})
    kind = planner.get("kind")
    if kind == "fixture_plan.v1":
        return FixturePlanPlanner(planner)
    if kind in {"gemini.v1", "openrouter.v1", "groq.v1"}:
        fallback_config = planner.get("fallback")
        if (
            not isinstance(fallback_config, dict)
            or fallback_config.get("kind") != "fixture_plan.v1"
        ):
            raise ValueError("MODEL_FALLBACK_PLAN_REQUIRED")
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
                    synthetic_values=fallback_config.get("synthetic_values", {}),
                )
        return ResilientPlanner(primary=primary, fallback=fallback)
    raise ValueError(f"Unsupported planner kind: {kind!r}")
