"""Build the accessibility report for one run: verdict, findings, rules, plain words.

The page, the HTML export and the JSON export all use ``build_report``, so they can
never disagree. Every sentence in the plain-words summary is rule-based: it is
written from the run's findings and outcome, not by an AI.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from engine.rules import SEVERITY_ORDER, rules_for_metadata

from .models import JourneyOutcome, Run, RunStatus

ACTIVE_STATUSES = {RunStatus.QUEUED, RunStatus.STARTING, RunStatus.RUNNING, RunStatus.FINALIZING}

RESULT_LABELS = {
    "passed": "Passed",
    "failed": "Failed",
    "needs_review": "Needs review",
    "not_applicable": "Not applicable",
    "not_checked": "Not checked",
    "disabled": "Turned off",
}

VERDICTS = {
    "running": ("Running", "neutral", "The evaluation is still running."),
    "blocked": (
        "Blocked",
        "issue",
        "A keyboard barrier stops the task. It was confirmed by a deterministic re-check.",
    ),
    "failing": ("Issues found", "issue", "The task can be done, but confirmed problems remain."),
    "review": ("Needs review", "warn", "Nothing was confirmed, but some items need a person."),
    "passed": ("Passed", "success", "The task was completed by keyboard with no failing rules."),
    "incomplete": (
        "Incomplete",
        "neutral",
        "The run stopped before the task could be judged; the site was not blamed.",
    ),
}


LOCATION_COLUMNS = (
    ("exact", "Exact match", "Rule-based: the element's own attributes in the code."),
    ("likely", "Likely cause", "Its text or classes, or the AI search's answer."),
    ("related", "Also affected", "Components that render it, or the same pattern elsewhere."),
)

METHOD_LABELS = {
    "tab_walk": "Tab walk from the top of the page",
    "activation_probe": "Enter, Space and click comparison",
    "trap_probe": "Tab, Shift+Tab and Escape trap test",
    "focus_diff": "Screenshots with and without focus",
    "point_sample": "Sampled points of the focused control",
    "dom_scan": "Page scan and accessibility tree",
    "observation": "Observed during the run",
    "axe": "axe-core",
}


def _rule_index(run: Run) -> dict[str, Any]:
    """Catalog rules plus the team's custom rules this run used."""
    return rules_for_metadata((run.planner_metadata or {}).get("rules"))


def can_view_code(run: Run, viewer: Any) -> bool:
    """Code from a linked repository is shown only to the person who linked it."""
    binding = run.journey.repo_binding
    return bool(
        binding is not None
        and viewer is not None
        and getattr(viewer, "pk", None) == binding.owner_id
    )


def _finding_rows(run: Run, show_code: bool = False) -> list[dict[str, Any]]:
    rules = _rule_index(run)
    rows = []
    for finding in run.findings.all():
        data = finding.data or {}
        rule = rules.get(finding.rule_id)
        locations = (data.get("locations") or None) if show_code else None
        columns = [
            {"label": label, "help": help_text, "items": (locations or {}).get(key) or []}
            for key, label, help_text in LOCATION_COLUMNS
        ]
        rows.append(
            {
                "pk": finding.pk,
                "locations": locations,
                "location_columns": columns,
                "can_verify": bool(
                    locations
                    and (locations.get("fix") or {}).get("edits")
                    and str((locations.get("fix") or {}).get("path", "")).startswith(
                        "fixtures/clinic/"
                    )
                ),
                "id": finding.finding_id,
                "rule_id": finding.rule_id,
                "title": finding.title,
                "summary": finding.summary,
                "severity": finding.severity,
                "status": finding.status,
                "source": finding.source,
                "ignored": finding.ignored,
                "ignore_reason": data.get("ignore_reason", ""),
                "wcag_criterion": finding.wcag_criterion,
                "wcag_level": data.get("wcag_level", ""),
                "step_number": finding.step_number,
                "url": finding.url,
                "element": data.get("element") or {},
                "occurrences": data.get("occurrences", 1),
                "examples": data.get("examples") or [],
                "confirmation": data.get("confirmation") or {},
                "help_url": data.get("help_url") or "",
                "fix_hints": list(rule.fix_hints) if rule else [],
                "rule_title": rule.title if rule else finding.title,
                "method_label": METHOD_LABELS.get(
                    (data.get("confirmation") or {}).get("method", ""),
                    (data.get("confirmation") or {}).get("method", "") or "—",
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row["ignored"],
            row["status"] != "confirmed",
            -SEVERITY_ORDER.get(row["severity"], 0),
            row["step_number"] or 0,
        )
    )
    return rows


def _verdict_key(run: Run, findings: list[dict[str, Any]], fail_on: str) -> str:
    if run.status in ACTIVE_STATUSES:
        return "running"
    if run.outcome == JourneyOutcome.BLOCKED:
        return "blocked"
    threshold = SEVERITY_ORDER.get(fail_on, 3)
    counted = [row for row in findings if not row["ignored"]]
    if any(
        row["status"] == "confirmed" and SEVERITY_ORDER.get(row["severity"], 0) >= threshold
        for row in counted
    ):
        return "failing"
    if run.outcome != JourneyOutcome.COMPLETED:
        return "incomplete"
    if counted:
        return "review"
    return "passed"


def _plain_words(run: Run, verdict: str, findings: list[dict[str, Any]]) -> str:
    confirmed = [row for row in findings if row["status"] == "confirmed" and not row["ignored"]]
    review = [row for row in findings if row["status"] == "needs_review" and not row["ignored"]]
    first = confirmed[0] if confirmed else None
    sentences: list[str] = []
    if verdict == "running":
        return "The evaluation is still running. This report fills in when it finishes."
    if verdict == "blocked" and first:
        step = f", step {first['step_number']}" if first["step_number"] else ""
        detail = first["summary"].rstrip(". ")
        sentences.append(
            f"A keyboard user cannot finish “{run.journey.name}”. {detail} "
            f"(WCAG {first['wcag_criterion']}, {first['severity']}{step})."
        )
    elif verdict == "blocked":
        sentences.append(f"A keyboard user cannot finish “{run.journey.name}”.")
    elif run.outcome == JourneyOutcome.COMPLETED:
        sentences.append(
            f"A keyboard user can finish “{run.journey.name}” using only the keyboard."
        )
    else:
        reason = run.diagnosis or "The run stopped before the task could be judged."
        sentences.append(f"The task was not finished, but the site was not blamed. {reason}")
    others = [row for row in confirmed if row is not first]
    if others:
        names = ", ".join(
            f"{row['rule_title'].lower()} (WCAG {row['wcag_criterion']})" for row in others[:3]
        )
        sentences.append(f"Also confirmed: {names}.")
    if review:
        sentences.append(
            f"{len(review)} item{' needs' if len(review) == 1 else 's need'} a person to review."
        )
    if verdict == "passed":
        sentences.append("No rule failed.")
    return " ".join(sentences)


def _duration(run: Run) -> str:
    if not (run.started_at and run.finished_at):
        return ""
    seconds = int((run.finished_at - run.started_at).total_seconds())
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def _rule_rows(run: Run) -> list[dict[str, Any]]:
    rules = _rule_index(run)
    rows = []
    for item in run.rule_results or []:
        rule = rules.get(item.get("rule_id", ""))
        if rule is None:
            continue
        rows.append(
            {
                "rule": rule,
                "result": item.get("result", "not_checked"),
                "label": RESULT_LABELS.get(item.get("result", ""), item.get("result", "")),
                "detail": item.get("detail", ""),
                "finding_count": item.get("finding_count", 0),
            }
        )
    return rows


def _ai_reasoning(run: Run) -> list[dict[str, Any]]:
    steps = []
    for step in run.steps.all():
        evidence = step.evidence or {}
        action = evidence.get("proposed_action") or {}
        steps.append(
            {
                "number": step.step_number,
                "action": str(action.get("action", "")).upper(),
                "target_hint": action.get("target_hint", ""),
                "purpose": action.get("purpose", ""),
                "policy": (evidence.get("policy_decision") or {}).get("code", ""),
                "result": (evidence.get("action_result") or {}).get("status", ""),
                "focus_after": (evidence.get("focus_after") or {}).get("name") or "Document body",
            }
        )
    return steps


def _repository(run: Run, show_code: bool = False) -> dict[str, Any] | None:
    binding = run.journey.repo_binding
    if binding is None:
        return None
    return {
        "is_owner": show_code,
        "journeys": [
            {"id": journey.pk, "name": journey.name}
            for journey in binding.journeys.filter(is_active=True).exclude(pk=run.journey_id)[:10]
        ],
        "name": binding.short_name,
        "branch": binding.branch,
        "commit": binding.commit_sha,
        "status": binding.status,
        "ready": binding.status == "ready",
    }


def build_report(run: Run, viewer: Any = None) -> dict[str, Any]:
    """The report as ``viewer`` may see it; code locations only for the repository owner."""
    show_code = can_view_code(run, viewer)
    findings = _finding_rows(run, show_code)
    rules_meta = (run.planner_metadata or {}).get("rules") or {}
    fail_on = rules_meta.get("fail_on", "serious")
    verdict = _verdict_key(run, findings, fail_on)
    label, tone, explanation = VERDICTS[verdict]
    rule_rows = _rule_rows(run)
    confirmed = [row for row in findings if row["status"] == "confirmed" and not row["ignored"]]
    review = [row for row in findings if row["status"] == "needs_review" and not row["ignored"]]
    ignored = [row for row in findings if row["ignored"]]
    by_severity: OrderedDict[str, list[dict[str, Any]]] = OrderedDict(
        (level, []) for level in ("critical", "serious", "moderate", "minor")
    )
    for row in confirmed:
        by_severity[row["severity"]].append(row)
    checked = [row for row in rule_rows if row["result"] in {"passed", "failed", "needs_review"}]
    passed = [row for row in rule_rows if row["result"] == "passed"]
    steps = run.steps.count()
    summary_parts = [
        f"{steps} keyboard step{'' if steps == 1 else 's'}",
        f"{len(confirmed)} confirmed finding{'' if len(confirmed) == 1 else 's'}",
        f"{len(review)} to review",
        f"{len(checked)} rules checked",
    ]
    duration = _duration(run)
    if duration:
        summary_parts.append(duration)
    metadata = run.planner_metadata or {}
    return {
        "schema_version": "accesspath_report.v1",
        "run_id": str(run.id),
        "journey": {
            "id": run.journey_id,
            "name": run.journey.name,
            "goal": run.journey.goal,
            "start_url": run.journey.start_url,
        },
        "verdict": {"key": verdict, "label": label, "tone": tone, "explanation": explanation},
        "summary_line": " · ".join(summary_parts),
        "plain_words": _plain_words(run, verdict, findings),
        "plain_words_source": "Rule-based",
        "outcome": run.outcome,
        "terminal_reason": run.terminal_reason,
        "failure_kind": run.failure_kind,
        "diagnosis": run.diagnosis,
        "stats": {
            "confirmed": len(confirmed),
            "review": len(review),
            "ignored": len(ignored),
            "rules_passed": len(passed),
            "rules_checked": len(checked),
            "steps": steps,
        },
        "findings": findings,
        "confirmed": confirmed,
        "review": review,
        "ignored": ignored,
        "by_severity": [(level, rows) for level, rows in by_severity.items() if rows],
        "rule_results": rule_rows,
        "rules": {
            "preset": rules_meta.get("preset", ""),
            "catalog_version": rules_meta.get("catalog_version", ""),
            "fail_on": fail_on,
        },
        "axe": (metadata.get("executor") or {}).get("axe") or {},
        "repository": _repository(run, show_code),
        "planner": {
            "provider": run.planner_provider,
            "model": metadata.get("model") or run.planner_model,
            "fallback_used": bool(metadata.get("fallback_used")),
        },
        "ai_steps": _ai_reasoning(run),
        "probe_events": metadata.get("probe_events") or [],
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration": duration,
    }


def report_json(report: dict[str, Any]) -> dict[str, Any]:
    """The export shape: plain data, no catalog objects."""
    data = dict(report)
    data["rule_results"] = [
        {
            "rule_id": row["rule"].id,
            "wcag": row["rule"].wcag.criterion,
            "title": row["rule"].title,
            "result": row["result"],
            "detail": row["detail"],
            "finding_count": row["finding_count"],
        }
        for row in report["rule_results"]
    ]
    for key in ("confirmed", "review", "ignored", "by_severity"):
        data.pop(key, None)
    return data
