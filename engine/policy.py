"""Deterministic keyboard-action policy module."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActionKind, ElementEvidenceV1, PolicyDecisionV1, ProposedActionV1


@dataclass(frozen=True)
class KeyboardActionPolicy:
    """Authorize only permitted keyboard actions at the current focused element."""

    max_policy_rejections_per_run: int = 2

    def decide(
        self,
        action: ProposedActionV1,
        focused_element: ElementEvidenceV1 | None,
        prior_same_code_rejections: int,
    ) -> PolicyDecisionV1:
        if action.action == ActionKind.TYPE and (
            focused_element is None
            or not focused_element.enabled
            or not focused_element.editable
        ):
            return PolicyDecisionV1(outcome="rejected", code="TYPE_TARGET_NOT_EDITABLE")
        if prior_same_code_rejections >= self.max_policy_rejections_per_run:
            return PolicyDecisionV1(outcome="rejected", code="POLICY_REJECTION_BUDGET_EXHAUSTED")
        return PolicyDecisionV1(outcome="approved", code="ACTION_ALLOWED")
