"""Collect findings during a run and turn them into per-rule results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .contracts import ElementDetailsV1, FindingConfirmationV1, FindingV1, RuleResultV1
from .rules import SEVERITY_ORDER, ActiveRuleSet, load_catalog, resolve_rules


@dataclass
class _RuleState:
    checked: bool = False
    applicable: bool = False
    not_checked_reason: str = ""
    detail: str = ""


@dataclass
class FindingCollector:
    """Holds one run's findings; merges repeats of the same problem on the same page."""

    rule_set: ActiveRuleSet = field(default_factory=lambda: resolve_rules({}))
    findings: list[FindingV1] = field(default_factory=list)
    _states: dict[str, _RuleState] = field(default_factory=dict)

    def is_active(self, rule_id: str) -> bool:
        return self.rule_set.is_active(rule_id)

    def checked(self, rule_id: str, *, applicable: bool, detail: str = "") -> None:
        """Record that a rule's check ran; ``applicable`` means the page had something to test."""
        state = self._states.setdefault(rule_id, _RuleState())
        state.checked = True
        if applicable and not state.applicable:
            # A "nothing to check here" note from an earlier page no longer applies.
            state.applicable = True
            state.detail = detail[:400]
        elif detail and not state.detail and applicable == state.applicable:
            state.detail = detail[:400]

    def not_checked(self, rule_id: str, reason: str) -> None:
        state = self._states.setdefault(rule_id, _RuleState())
        if not state.checked:
            state.not_checked_reason = reason[:400]

    def add(
        self,
        rule_id: str,
        *,
        summary: str,
        url: str,
        method: str,
        detail: str = "",
        confirmed: bool = True,
        element: ElementDetailsV1 | dict | None = None,
        step_number: int | None = None,
        title: str | None = None,
        severity: str | None = None,
        merge_key: str | None = None,
    ) -> FindingV1 | None:
        """Add a finding for an active rule; returns None when the rule is not active."""
        active = self.rule_set.get(rule_id)
        if active is None:
            return None
        rule = active.rule
        details = (
            element
            if isinstance(element, ElementDetailsV1) or element is None
            else ElementDetailsV1.model_validate(element)
        )
        self.checked(rule_id, applicable=True)
        key = merge_key or (details.css_path if details else "") or summary
        finding_id = hashlib.sha256(f"{rule_id}|{_page(url)}|{key}".encode()).hexdigest()[:16]
        existing = next((item for item in self.findings if item.id == finding_id), None)
        if existing is not None:
            path = details.css_path if details else ""
            seen = bool(path) and any(example.css_path == path for example in existing.examples)
            if not seen:
                existing.occurrences += 1
                if details and len(existing.examples) < 5:
                    existing.examples.append(details)
            if confirmed and existing.status != "confirmed":
                # A probe confirmed what a scan only suspected: its wording replaces the scan's.
                existing.status = "confirmed"
                existing.summary = summary[:800]
                existing.step_number = step_number or existing.step_number
                existing.element = details or existing.element
                existing.confirmation = FindingConfirmationV1(
                    method=method,  # type: ignore[arg-type]
                    confirmed=True,
                    detail=detail[:600],
                )
            return existing
        ignore = self.rule_set.ignore_for(
            rule_id,
            details.css_path if details else None,
            details.name if details else None,
            details.html_snippet if details else None,
        )
        finding = FindingV1(
            id=finding_id,
            rule_id=rule_id,
            wcag_criterion=rule.wcag.criterion,
            wcag_level=rule.wcag.level,
            severity=severity or active.severity,  # type: ignore[arg-type]
            status="confirmed" if confirmed else "needs_review",
            title=(title or rule.title)[:200],
            summary=summary[:800],
            step_number=step_number,
            url=url[:1000],
            element=details,
            examples=[details] if details else [],
            confirmation=FindingConfirmationV1(
                method=method,  # type: ignore[arg-type]
                confirmed=confirmed,
                detail=detail[:600],
            ),
            ignored=ignore is not None,
            ignore_reason=ignore.reason if ignore else "",
            help_url=str(rule.wcag.url),
        )
        self.findings.append(finding)
        return finding

    def add_external(self, finding: FindingV1) -> None:
        """Add a finding from another tool (axe-core) that already carries its own rule id."""
        if not any(item.id == finding.id for item in self.findings):
            self.findings.append(finding)

    def results(self) -> list[RuleResultV1]:
        """One result per catalog rule, so a pass never secretly means 'not checked'."""
        catalog = load_catalog()
        results: list[RuleResultV1] = []
        custom = [
            catalog_rule for item in self.rule_set.custom if (catalog_rule := item.as_rule(catalog))
        ]
        for rule in [*catalog.rules, *custom]:
            if rule.id in self.rule_set.disabled:
                results.append(
                    RuleResultV1(
                        rule_id=rule.id,
                        result="disabled",
                        detail=self.rule_set.disabled[rule.id],
                    )
                )
                continue
            if not self.rule_set.is_active(rule.id):
                continue
            own = [item for item in self.findings if item.rule_id == rule.id]
            state = self._states.get(rule.id, _RuleState())
            if any(item.status == "confirmed" for item in own):
                result = "failed"
            elif own:
                result = "needs_review"
            elif state.checked and state.applicable:
                result = "passed"
            elif state.checked:
                result = "not_applicable"
            else:
                result = "not_checked"
            # A pass or "not applicable" note never explains a failure.
            detail = (
                ""
                if result in {"failed", "needs_review"}
                else (state.detail or state.not_checked_reason)
            )
            if result == "not_checked" and not detail:
                detail = "The run ended before this rule could be checked."
            results.append(
                RuleResultV1(rule_id=rule.id, result=result, detail=detail, finding_count=len(own))
            )
        return results

    def sorted_findings(self) -> list[FindingV1]:
        return sorted(
            self.findings,
            key=lambda item: (
                item.ignored,
                item.status != "confirmed",
                -SEVERITY_ORDER.get(item.severity, 0),
                item.step_number or 0,
            ),
        )


def element_signature(kind: str, element: ElementDetailsV1 | dict | None) -> str:
    """Group copies of the same control (for example three identical slot buttons)."""
    if element is None:
        return kind
    data = element.model_dump() if isinstance(element, ElementDetailsV1) else element
    classes = ".".join(sorted(data.get("classes") or []))
    return f"{kind}|{data.get('tag')}|{data.get('role')}|{classes}|{data.get('tabindex')}"


def _page(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0]
