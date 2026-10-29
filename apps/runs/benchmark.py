"""Gate 1 metrics for benchmark journeys with known expected results."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from statistics import median
from typing import Any

from .models import Run

TRUSTWORTHY_OUTCOMES = {"completed", "blocked"}

# Phase 1 gate from the plan doc.
GATE_1 = {
    "trustworthy_rate": 0.80,
    "barrier_precision": 0.90,
    "repeatability": 0.80,
    "known_barriers_found": 0.70,
    "within_free_tier_rate": 0.70,
}


@dataclass
class BenchmarkResult:
    journey_key: str
    run_id: str
    expected_outcome: str
    expected_rules: list[str]
    outcome: str
    terminal_reason: str
    failure_kind: str
    confirmed_rules: list[str]
    duration_seconds: float | None = None
    extra_rules: list[str] = field(default_factory=list)
    missed_rules: list[str] = field(default_factory=list)

    @property
    def matches(self) -> bool:
        return self.outcome == self.expected_outcome and sorted(self.confirmed_rules) == sorted(
            self.expected_rules
        )


def result_for(run: Run) -> BenchmarkResult:
    expected = run.journey.evaluation_config.get("benchmark") or {}
    confirmed = sorted(
        {
            finding.rule_id
            for finding in run.findings.all()
            if finding.status == "confirmed"
            and not finding.ignored
            and finding.source == "accesspath"
            # Team rules are each team's own policy, not part of the benchmark's ground truth.
            and not finding.rule_id.startswith("custom-")
        }
    )
    expected_rules = sorted(expected.get("confirmed_rules", []))
    duration = None
    if run.started_at and run.finished_at:
        duration = (run.finished_at - run.started_at).total_seconds()
    return BenchmarkResult(
        journey_key=run.journey.evaluation_config.get("journey_key", run.journey.name),
        run_id=str(run.id),
        expected_outcome=expected.get("outcome", ""),
        expected_rules=expected_rules,
        outcome=run.outcome,
        terminal_reason=run.terminal_reason,
        failure_kind=run.failure_kind,
        confirmed_rules=confirmed,
        duration_seconds=duration,
        extra_rules=[rule for rule in confirmed if rule not in expected_rules],
        missed_rules=[rule for rule in expected_rules if rule not in confirmed],
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def summarize(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Compute the Gate 1 measures from a list of benchmark run results."""
    total = len(results)
    confirmed_total = sum(len(item.confirmed_rules) for item in results)
    confirmed_correct = sum(
        len([rule for rule in item.confirmed_rules if rule in item.expected_rules])
        for item in results
    )
    expected_total = sum(len(item.expected_rules) for item in results)
    expected_found = sum(
        len([rule for rule in item.expected_rules if rule in item.confirmed_rules])
        for item in results
    )
    by_journey: dict[str, list[BenchmarkResult]] = defaultdict(list)
    for item in results:
        by_journey[item.journey_key].append(item)
    repeated = {key: items for key, items in by_journey.items() if len(items) > 1}
    consistent = sum(
        1
        for items in repeated.values()
        if len({(item.outcome, tuple(item.confirmed_rules)) for item in items}) == 1
    )
    quota_hits = sum(1 for item in results if "QUOTA" in item.terminal_reason)
    durations = [item.duration_seconds for item in results if item.duration_seconds is not None]
    metrics = {
        "runs": total,
        "journeys": len(by_journey),
        "trustworthy_rate": _rate(
            sum(1 for item in results if item.outcome in TRUSTWORTHY_OUTCOMES), total
        ),
        "expected_result_rate": _rate(sum(1 for item in results if item.matches), total),
        "barrier_precision": _rate(confirmed_correct, confirmed_total),
        "known_barriers_found": _rate(expected_found, expected_total),
        "repeatability": _rate(consistent, len(repeated)),
        "within_free_tier_rate": _rate(total - quota_hits, total),
        "median_seconds": round(median(durations), 1) if durations else None,
    }
    gate = {
        name: (None if metrics[name] is None else metrics[name] >= target)
        for name, target in GATE_1.items()
    }
    return {
        "metrics": metrics,
        "gate_1": {"targets": GATE_1, "met": gate},
        "results": [asdict(item) | {"matches": item.matches} for item in results],
    }
