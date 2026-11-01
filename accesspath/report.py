"""CLI reports: a JSON summary, a Markdown PR comment, SARIF for code scanning, baselines."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from engine.rules import SEVERITY_ORDER, rules_for_metadata

from . import __version__
from .runner import RunOutput

VERDICTS = {
    "blocked": (
        "Blocked",
        "A keyboard barrier stops the task; a deterministic re-check confirmed it.",
    ),
    "failing": ("Issues found", "The task can be done, but confirmed problems remain."),
    "review": ("Needs review", "Nothing failed, but some items need a person to look."),
    "passed": ("Passed", "The task was completed by keyboard with no failing rules."),
    "incomplete": (
        "Incomplete",
        "The run stopped before the task could be judged; the site was not blamed.",
    ),
}
# Exit codes: 0 passed or only review items, 1 failing, 2 blocked, 3 incomplete, 4 setup error.
EXIT_CODES = {"passed": 0, "review": 0, "failing": 1, "blocked": 2, "incomplete": 3}
COMMENT_MARKER = "<!-- accesspath-report -->"


def stable_id(row: dict[str, Any]) -> str:
    """The same finding on the same page gets the same id on every run, whatever the host
    and port (a local site folder is served on a new port each time)."""
    element = row.get("element") or {}
    parsed = urlparse(row.get("url", ""))
    page = parsed.path or "/"
    # Without an element, the summary tells findings apart (the engine does the same);
    # the origin is removed so a new port does not change the id.
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
    text = str(row.get("summary") or row.get("title", ""))
    key = element.get("css_path") or (text.replace(origin, "") if origin else text)
    return hashlib.sha256(f"{row['rule_id']}|{page}|{key}".encode()).hexdigest()[:16]


def _verdict(
    output: RunOutput, findings: list[dict[str, Any]], fail_on: str, baseline_used: bool
) -> str:
    result = output.result
    counted = [row for row in findings if not row["ignored"] and not row.get("baseline_known")]
    if result.outcome == "blocked" and any(
        row["status"] == "confirmed" for row in findings if not row.get("baseline_known")
    ):
        return "blocked"
    threshold = SEVERITY_ORDER.get(fail_on, 3)
    if any(
        row["status"] == "confirmed" and SEVERITY_ORDER.get(row["severity"], 0) >= threshold
        for row in counted
    ):
        return "failing"
    if result.outcome == "blocked":
        if not baseline_used:
            return "blocked"
        return "review" if counted else "passed"  # The barrier is a known baseline item.
    if result.outcome != "completed":
        return "incomplete"
    return "review" if counted else "passed"


def build_summary(
    output: RunOutput,
    *,
    fail_on: str | None = None,
    baseline: dict[str, Any] | None = None,
    journey_path: str = "",
) -> dict[str, Any]:
    fail_on = fail_on or output.rule_set.fail_on
    known = {item.get("stable_id") or item["id"] for item in (baseline or {}).get("findings", [])}
    rules = rules_for_metadata(output.rule_set.to_metadata())
    findings = []
    for finding in output.result.findings:
        data = finding.model_dump(mode="json")
        rule = rules.get(finding.rule_id)
        data["rule_title"] = rule.title if rule else finding.title
        data["fix_hints"] = list(rule.fix_hints) if rule else []
        data["locations"] = output.locations.get(finding.id)
        data["stable_id"] = stable_id(data)
        data["baseline_known"] = bool(baseline) and data["stable_id"] in known
        findings.append(data)
    findings.sort(
        key=lambda row: (
            row["ignored"],
            row["status"] != "confirmed",
            -SEVERITY_ORDER.get(row["severity"], 0),
        )
    )
    verdict = _verdict(output, findings, fail_on, bool(baseline))
    label, explanation = VERDICTS[verdict]
    if (
        baseline
        and verdict in {"passed", "review"}
        and any(row["baseline_known"] for row in findings)
    ):
        explanation = "Nothing new compared with the baseline; the known problems below remain."
    ids = {row["stable_id"] for row in findings}
    return {
        "schema_version": "accesspath_cli_report.v1",
        "tool": {"name": "AccessPath AI", "version": __version__},
        "created_at": datetime.now(UTC).isoformat(),
        "journey": {
            "name": output.journey.name,
            "goal": output.journey.goal,
            "start_url": output.start_url,
            "file": journey_path,
        },
        "planner": {
            "provider": output.provider,
            "model": output.model,
            "usage": output.planner_metadata.get("usage"),
        },
        "verdict": {"key": verdict, "label": label, "explanation": explanation},
        "exit_code": EXIT_CODES[verdict],
        "fail_on": fail_on,
        "outcome": output.result.outcome,
        "terminal_reason": output.result.terminal_reason,
        "failure_kind": output.result.failure_kind,
        "diagnosis": output.result.diagnosis,
        "steps": len(output.steps),
        "findings": findings,
        "rule_results": [item.model_dump(mode="json") for item in output.result.rule_results],
        "rules": output.rule_set.to_metadata(),
        "baseline": {
            "used": bool(baseline),
            "new": [row["stable_id"] for row in findings if baseline and not row["baseline_known"]],
            "fixed": sorted(known - ids) if baseline else [],
        },
    }


def _where(row: dict[str, Any]) -> tuple[str, int] | None:
    locations = row.get("locations") or {}
    for column in ("exact", "likely"):
        items = locations.get(column) or []
        if items:
            return items[0]["path"], int(items[0]["line"])
    return None


def _md(text: Any) -> str:
    """Page text in a PR comment: one line, no table breaks, no code spans, no @mentions
    (it comes from the tested site), and URLs without their query strings."""
    text = re.sub(r"(https?://[^\s?#]+)[?#]\S*", r"\1", str(text or ""))
    text = text.replace("\n", " ").replace("|", "\\|").replace("`", "'")
    return re.sub(r"@(?=\w)", "@\u200b", text)


def _without_query(url: str) -> str:
    return url.split("?", 1)[0].split("#", 1)[0]


def to_markdown(summary: dict[str, Any]) -> str:
    verdict = summary["verdict"]
    journey = summary["journey"]
    lines = [
        COMMENT_MARKER,
        f"## AccessPath AI: {verdict['label']} — {journey['name']}",
        "",
        f"{verdict['explanation']}",
        "",
        f"Goal: {_md(journey['goal'])}  ",
        f"Planner: {summary['planner']['provider']}"
        + (f" ({summary['planner']['model']})" if summary["planner"]["model"] else "")
        + f" · {summary['steps']} keyboard steps · fails on {summary['fail_on']} and above",
    ]
    if summary["diagnosis"]:
        lines += ["", f"> {_md(summary['diagnosis'])}"]
    baseline = summary["baseline"]
    if baseline["used"]:
        lines += [
            "",
            f"Compared with the baseline: {len(baseline['new'])} new, "
            f"{len(baseline['fixed'])} fixed.",
        ]
    rows = [row for row in summary["findings"] if not row["ignored"]]
    if rows:
        lines += [
            "",
            "| Severity | WCAG | Finding | Where to fix |",
            "|---|---|---|---|",
        ]
        for row in rows[:20]:
            where = _where(row)
            place = f"`{where[0]}:{where[1]}`" if where else "—"
            status = "" if row["status"] == "confirmed" else " (review)"
            new = " **new**" if baseline["used"] and not row["baseline_known"] else ""
            text = _md(row["summary"])[:300]
            lines.append(
                f"| {row['severity']}{status}{new} | {row['wcag_criterion'] or '—'} | "
                f"**{row['rule_title']}**: {text} | {place} |"
            )
        if len(rows) > 20:
            lines.append(f"\n…and {len(rows) - 20} more in the full report.")
    else:
        lines += ["", "No findings."]
    fixes = [
        row
        for row in rows
        if (row.get("locations") or {}).get("fix", {}) and row["locations"]["fix"].get("patch")
    ]
    for row in fixes[:3]:
        fix = row["locations"]["fix"]
        patch = fix["patch"].rstrip()
        longest = max((len(run) for run in re.findall(r"`+", patch)), default=0)
        fence = "`" * max(3, longest + 1)
        lines += [
            "",
            f"<details><summary>Suggested patch: {_md(fix['title'])} (`{fix['path']}`)</summary>",
            "",
            f"{fence}diff",
            patch,
            fence,
            "</details>",
        ]
    lines += [
        "",
        f"<sub>AccessPath AI {summary['tool']['version']} · keyboard-only profile · "
        "results do not claim full WCAG conformance</sub>",
    ]
    return "\n".join(lines) + "\n"


def _sarif_level(row: dict[str, Any], fail_on: str) -> str:
    if row["status"] != "confirmed":
        return "note"
    if SEVERITY_ORDER.get(row["severity"], 0) >= SEVERITY_ORDER.get(fail_on, 3):
        return "error"
    return "warning"


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "journey"


def git_relative(path: Path) -> tuple[str, Path | None]:
    """``path`` relative to its git checkout's root, with forward slashes (SARIF wants
    paths from the repository root); ("", None) when it is not inside a checkout."""
    path = path.resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            relative = path.relative_to(parent).as_posix()
            return ("" if relative == "." else relative), parent
    return "", None


def to_sarif(summary: dict[str, Any]) -> dict[str, Any]:
    """SARIF 2.1.0 for GitHub code scanning; results point at the code to fix."""
    rule_ids: list[str] = []
    rules: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    code_root = summary.get("code_root") or ""
    fallback_file = summary["journey"].get("sarif_file") or "accesspath-journey.json"
    for row in summary["findings"]:
        if row["ignored"]:
            continue
        if row["rule_id"] not in rule_ids:
            rule_ids.append(row["rule_id"])
            rules.append(
                {
                    "id": row["rule_id"],
                    "name": row["rule_id"].replace("/", "_"),
                    "shortDescription": {"text": row["rule_title"][:200]},
                    "helpUri": row.get("help_url") or "https://www.w3.org/TR/WCAG22/",
                    "help": {"text": " ".join(row.get("fix_hints") or [row["rule_title"]])[:1000]},
                    "properties": {
                        "tags": ["accessibility", "keyboard"]
                        + ([f"WCAG {row['wcag_criterion']}"] if row["wcag_criterion"] else []),
                    },
                }
            )
        where = _where(row)
        path, line = where if where else (fallback_file, 1)
        if where and code_root:
            path = f"{code_root}/{path}"
        message = row["summary"]
        if not where:
            message += f" (Found on {_without_query(row['url'])}; no matching code was located.)"
        results.append(
            {
                "ruleId": row["rule_id"],
                "ruleIndex": rule_ids.index(row["rule_id"]),
                "level": _sarif_level(row, summary["fail_on"]),
                "message": {"text": message[:2000]},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": path, "uriBaseId": "%SRCROOT%"},
                            "region": {"startLine": max(1, line)},
                        }
                    }
                ],
                "partialFingerprints": {"accesspathFinding/v1": row["stable_id"]},
                "properties": {
                    "severity": row["severity"],
                    "status": row["status"],
                    "wcag": row["wcag_criterion"],
                    "page": _without_query(row["url"]),
                },
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AccessPath AI",
                        "version": summary["tool"]["version"],
                        "informationUri": "https://github.com/MICKEY0107/AccessPath-AI",
                        "rules": rules,
                    }
                },
                # The text before the last "/" is the code-scanning category: one per
                # journey, so uploads for different journeys never replace each other.
                "automationDetails": {"id": f"accesspath/{_slug(summary['journey']['name'])}/"},
                "results": results,
            }
        ],
    }
