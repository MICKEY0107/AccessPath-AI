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
    # Accessible name of the element focused after the action, so a planner can see
    # that repeated Tabs are cycling through the same controls.
    focus_after: str | None = Field(default=None, max_length=120)
    target_hint: str = Field(default="", max_length=120)
    # The permitted value a Type action entered, so the planner can see which items
    # it already added and move on to the next one.
    typed_value: str | None = Field(default=None, max_length=256)


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
    # Every value typed so far in this run, in order; history alone keeps only 8 turns.
    typed_values: list[str] = Field(default_factory=list, max_length=20)
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
        "url_contains",
        "text_present",
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
    allowed_methods: list[Literal["GET", "HEAD", "OPTIONS", "POST"]] = Field(
        default_factory=lambda: ["GET", "HEAD", "OPTIONS"],
        min_length=1,
        max_length=4,
    )
    # Staging only: POST (form submissions) is allowed solely to these origins, which
    # must also be navigation origins, and at most ``max_writes`` times per run.
    write_origins: list[str] = Field(default_factory=list, max_length=3)
    max_writes: int = Field(default=0, ge=0, le=20)
    allow_popups: Literal[False] = False
    allow_downloads: Literal[False] = False
    # Real sites load images, fonts, and scripts from many CDNs. When true, read-only
    # (GET/HEAD/OPTIONS) subresources may come from any public origin; navigation stays
    # limited to navigation_origins and private or local hosts stay blocked.
    allow_any_resource_origin: bool = False
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

    @model_validator(mode="after")
    def writes_are_bounded(self) -> TargetPolicyV1:
        if "POST" in self.allowed_methods:
            if not self.write_origins or self.max_writes < 1:
                raise ValueError("POST needs write_origins and max_writes (staging only)")
            if not set(self.write_origins) <= set(self.navigation_origins):
                raise ValueError("write_origins must be navigation origins")
        elif self.write_origins or self.max_writes:
            raise ValueError("write_origins and max_writes need POST in allowed_methods")
        return self


class ElementDetailsV1(BaseModel):
    """Element facts that let a person (or the code mapper) find it in the source.

    Never includes typed values: input values and password fields are stripped from
    the HTML snippet before it leaves the browser.
    """

    model_config = ConfigDict(extra="forbid")

    tag: str | None = Field(default=None, max_length=32)
    role: str | None = Field(default=None, max_length=64)
    name: str = Field(default="", max_length=200)
    test_id: str | None = Field(default=None, max_length=128)
    dom_id: str | None = Field(default=None, max_length=128)
    classes: list[str] = Field(default_factory=list, max_length=12)
    css_path: str = Field(default="", max_length=512)
    html_snippet: str = Field(default="", max_length=400)
    tabindex: str | None = Field(default=None, max_length=8)
    rect: dict[str, float] | None = None
    source_file: str | None = Field(default=None, max_length=300)
    source_line: int | None = Field(default=None, ge=1)
    framework: str | None = Field(default=None, max_length=16)

    @field_validator("classes")
    @classmethod
    def classes_are_short(cls, values: list[str]) -> list[str]:
        return [value[:64] for value in values if value][:12]


FindingMethod = Literal[
    "tab_walk",
    "activation_probe",
    "trap_probe",
    "focus_diff",
    "point_sample",
    "dom_scan",
    "observation",
    "axe",
]


class FindingConfirmationV1(BaseModel):
    """How AccessPath checked a finding before reporting it."""

    model_config = ConfigDict(extra="forbid")

    method: FindingMethod
    confirmed: bool
    detail: str = Field(default="", max_length=600)


class FindingV1(BaseModel):
    """One accessibility problem, tied to a catalog rule and its evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["finding.v1"] = "finding.v1"
    id: str = Field(min_length=8, max_length=64)
    rule_id: str = Field(max_length=96)
    wcag_criterion: str = Field(default="", max_length=16)
    wcag_level: str = Field(default="", max_length=4)
    severity: Literal["critical", "serious", "moderate", "minor"]
    status: Literal["confirmed", "needs_review"]
    source: Literal["accesspath", "axe"] = "accesspath"
    title: str = Field(max_length=200)
    summary: str = Field(max_length=800)
    step_number: int | None = Field(default=None, ge=1)
    url: str = Field(max_length=1000)
    element: ElementDetailsV1 | None = None
    occurrences: int = Field(default=1, ge=1)
    examples: list[ElementDetailsV1] = Field(default_factory=list, max_length=5)
    confirmation: FindingConfirmationV1
    ignored: bool = False
    ignore_reason: str = Field(default="", max_length=240)
    help_url: str | None = Field(default=None, max_length=500)


class RuleResultV1(BaseModel):
    """Whether one rule passed, failed, did not apply, or was not checked in a run."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(max_length=96)
    result: Literal["passed", "failed", "needs_review", "not_applicable", "not_checked", "disabled"]
    detail: str = Field(default="", max_length=400)
    finding_count: int = Field(default=0, ge=0)
