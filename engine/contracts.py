"""Versioned engine contracts shared by planner, policy, executor, and reporting."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class ActionKind(StrEnum):
    TAB = "tab"
    SHIFT_TAB = "shift_tab"
    ENTER = "enter"
    SPACE = "space"
    ARROW_UP = "arrow_up"
    ARROW_DOWN = "arrow_down"
    ARROW_LEFT = "arrow_left"
    ARROW_RIGHT = "arrow_right"
    ESCAPE = "escape"
    TYPE = "type"


class ElementEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=256)

    fingerprint: str
    role: str | None = None
    name: str | None = None
    test_id: str | None = None
    tag: str | None = None
    control_type: str | None = None
    label: str | None = None
    editable: bool = False
    enabled: bool = True
    expanded: bool | None = None
    checked: bool | None = None
    selected: bool | None = None
    required: bool = False
    active_descendant: str | None = None
    href: str | None = Field(default=None, max_length=512)
    frame: str = "main"


class ProposedActionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=256)

    action: ActionKind
    value: str | None = None
    target_hint: str = ""
    purpose: str = ""

    @field_validator("value")
    @classmethod
    def type_action_requires_nonempty_value(cls, value: str | None, info) -> str | None:
        if info.data.get("action") == ActionKind.TYPE and not value:
            raise ValueError("type actions require a non-empty value")
        if info.data.get("action") != ActionKind.TYPE and value is not None:
            raise ValueError("only type actions may include a value")
        return value


class PlannerHistoryEntryV1(BaseModel):
    """Privacy-minimized result from one previous planner turn."""

    model_config = ConfigDict(extra="forbid", str_max_length=256)

    action: ActionKind
    policy_code: str = Field(max_length=64)
    result_status: Literal[
        "effect_observed",
        "no_effect",
        "wrong_effect",
        "focus_lost",
        "repeated_focus_cycle",
        "navigation_blocked",
        "rejected",
        "execution_error",
    ]
    meaningful_progress: bool


class PlannerInteractiveElementV1(BaseModel):
    """Bounded, sanitized interactive-element summary supplied to a planner."""

    model_config = ConfigDict(extra="forbid", str_max_length=120)

    role: str | None = None
    name: str = ""
    test_id: str | None = None
    tag: str | None = None
    control_type: str | None = None
    label: str | None = None
    editable: bool = False
    enabled: bool = True
    expanded: bool | None = None
    checked: bool | None = None
    selected: bool | None = None
    required: bool = False
    active_descendant: str | None = None
    href: str | None = Field(default=None, max_length=512)
    frame: str = "main"


class PlannerObservationV1(BaseModel):
    """Bounded page state; excludes HTML, scripts, hidden values, and credentials."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["planner_observation.v1"] = "planner_observation.v1"
    goal: str = Field(min_length=1, max_length=512)
    url: HttpUrl
    focused_element: ElementEvidenceV1 | None = None
    interactive_elements: list[PlannerInteractiveElementV1] = Field(
        default_factory=list, max_length=40
    )
    visible_text: str = Field(default="", max_length=4000)
    history: list[PlannerHistoryEntryV1] = Field(default_factory=list, max_length=8)
    permitted_inputs: dict[str, str] = Field(default_factory=dict, max_length=10)
    remaining_steps: int = Field(ge=0, le=100)
    elements_truncated: bool = False
    visible_text_truncated: bool = False
    history_truncated: bool = False

    @field_validator("permitted_inputs")
    @classmethod
    def permitted_inputs_are_bounded(cls, values: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 64 or len(value) > 256 for key, value in values.items()):
            raise ValueError("permitted input keys or values exceed their bounds")
        return values


class PolicyDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["approved", "rejected"]
    code: str = Field(max_length=64)


class ActionResultV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "effect_observed",
        "no_effect",
        "wrong_effect",
        "focus_lost",
        "repeated_focus_cycle",
        "navigation_blocked",
        "rejected",
        "execution_error",
    ]
    meaningful_progress: bool
    error_code: str | None = Field(default=None, max_length=64)


class ArtifactRefV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    kind: Literal["screenshot_before", "screenshot_after", "trace", "axe_raw"]
    sha256: str = Field(min_length=64, max_length=64)


class StepEvidenceV1(BaseModel):
    """Immutable keyboard-observation record for one proposed action."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["step_evidence.v1"] = "step_evidence.v1"
    run_id: UUID
    step_number: int = Field(ge=1)
    observed_at: datetime
    url_before: HttpUrl
    url_after: HttpUrl
    focus_before: ElementEvidenceV1 | None = None
    focus_after: ElementEvidenceV1 | None = None
    proposed_action: ProposedActionV1
    policy_decision: PolicyDecisionV1
    executed_action: ProposedActionV1 | None = None
    action_result: ActionResultV1
    state_fingerprint_before: str = Field(min_length=8, max_length=128)
    state_fingerprint_after: str = Field(min_length=8, max_length=128)
    duration_ms: int = Field(ge=0)
    artifact_refs: list[ArtifactRefV1] = Field(default_factory=list)
    rule_evaluation_refs: list[UUID] = Field(default_factory=list)
    policy_events: list[str] = Field(default_factory=list, max_length=20)
    evidence_events: list[str] = Field(default_factory=list, max_length=20)
    completion_signals: dict[str, bool] = Field(default_factory=dict, max_length=10)
    evidence_source: Literal["keyboard_observation"] = "keyboard_observation"

    @field_validator("executed_action")
    @classmethod
    def rejected_actions_are_never_executed(
        cls, value: ProposedActionV1 | None, info
    ) -> ProposedActionV1 | None:
        decision = info.data.get("policy_decision")
        if decision and decision.outcome == "rejected" and value is not None:
            raise ValueError("rejected actions cannot have executed_action")
        return value


class CompletionLocatorV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: Literal["test_id", "role", "heading"]
    value: str = Field(min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=256)
    level: int | None = Field(default=None, ge=1, le=6)

    @model_validator(mode="after")
    def locator_fields_match_strategy(self) -> CompletionLocatorV1:
        if self.by == "heading" and self.level is None:
            raise ValueError("heading locators require a level")
        if self.by != "heading" and self.level is not None:
            raise ValueError("only heading locators may include a level")
        if self.by != "role" and self.name is not None:
            raise ValueError("only role locators may include a name")
        return self


class CompletionSignalV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    type: Literal[
        "url_path_equals",
        "element_present",
        "element_text_equals",
        "element_attribute_equals",
    ]
    locator: CompletionLocatorV1 | None = None
    expected: str | None = Field(default=None, max_length=256)
    attribute: str | None = Field(default=None, max_length=64)
    case_sensitive: bool = True


class CompletionStabilityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consecutive_observations: Literal[2] = 2
    interval_ms: Literal[500] = 500


class CompletionPolicyV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["completion_policy.v1"] = "completion_policy.v1"
    mode: Literal["all"] = "all"
    signals: list[CompletionSignalV1] = Field(min_length=1, max_length=5)
    stability: CompletionStabilityV1 = Field(default_factory=CompletionStabilityV1)

    @field_validator("signals")
    @classmethod
    def signal_ids_are_unique(cls, signals: list[CompletionSignalV1]) -> list[CompletionSignalV1]:
        if len({signal.id for signal in signals}) != len(signals):
            raise ValueError("completion signal IDs must be unique")
        return signals


class TargetPolicyV1(BaseModel):
    """Fail-closed network and browser-event boundary for one approved target."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["target_policy.v1"] = "target_policy.v1"
    navigation_origins: list[str] = Field(min_length=1, max_length=10)
    resource_origins: list[str] = Field(min_length=1, max_length=20)
    navigation_path_prefixes: list[str] = Field(min_length=1, max_length=20)
    allowed_methods: list[Literal["GET", "HEAD", "OPTIONS"]] = Field(
        default_factory=lambda: ["GET", "HEAD", "OPTIONS"],
        min_length=1,
        max_length=3,
    )
    allow_popups: Literal[False] = False
    allow_downloads: Literal[False] = False
    block_service_workers: bool = True
    max_pages: int = Field(default=1, ge=1, le=5)
    total_timeout_ms: int = Field(default=300_000, ge=1_000, le=900_000)
    no_progress_limit: int = Field(default=4, ge=2, le=20)
    max_actions: int = Field(default=40, ge=1, le=100)
    user_agent: str = Field(
        default="AccessPathAI-local-pilot/0.1 keyboard-accessibility-evaluator",
        min_length=10,
        max_length=256,
    )

    @field_validator("navigation_origins", "resource_origins")
    @classmethod
    def origins_are_exact(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            parsed = urlparse(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.params
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError("origins must not include a path, credentials, query, or fragment")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in normalized:
                normalized.append(origin)
        return normalized

    @field_validator("navigation_path_prefixes")
    @classmethod
    def path_prefixes_are_absolute(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("/") or "?" in value or "#" in value for value in values):
            raise ValueError("navigation path prefixes must be absolute paths")
        return list(dict.fromkeys(values))
