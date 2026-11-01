"""Run one journey file with the web app's engine, without a server or database."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from engine.artifacts import LocalArtifactStore
from engine.code_index import build_index
from engine.code_locator import locate
from engine.contracts import StepEvidenceV1
from engine.executor import EvaluationResult, KeyboardExecutor
from engine.fixture_site import serve_directory
from engine.planner import planner_from_config
from engine.rules import ActiveRuleSet, load_catalog, resolve_rules
from engine.session_state import limit_to_origins

from .journey_file import JourneyFileV1

PROVIDERS = ("scripted", "groq", "gemini", "openrouter", "ollama")
KEY_ENV = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
MODEL_ENV = {
    "groq": "GROQ_MODEL",
    "gemini": "GEMINI_MODEL",
    "openrouter": "OPENROUTER_MODEL",
    "ollama": "OLLAMA_MODEL",
}
USER_AGENT = "AccessPathAI-cli/1.0 keyboard-accessibility-evaluator"


class RunConfigError(ValueError):
    """A plain-language reason the run could not start."""


@dataclass
class RunOutput:
    journey: JourneyFileV1
    provider: str
    model: str
    start_url: str
    result: EvaluationResult
    rule_set: ActiveRuleSet
    steps: list[StepEvidenceV1] = field(default_factory=list)
    locations: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts_dir: Path | None = None
    planner_metadata: dict[str, Any] = field(default_factory=dict)


@contextmanager
def _site(journey: JourneyFileV1, base_dir: Path) -> Iterator[str]:
    if journey.site_dir:
        root = (base_dir / journey.site_dir).resolve()
        with serve_directory(root) as origin:
            yield origin
    else:
        parsed = urlparse(journey.start_url or "")
        yield f"{parsed.scheme}://{parsed.netloc}"


def _client(provider: str, api_key: str):
    timeout = float(os.environ.get("PLANNER_CALL_TIMEOUT_SECONDS", "30"))
    interval = float(os.environ.get("PLANNER_MIN_CALL_INTERVAL_SECONDS", "4"))
    if provider == "groq":
        from engine.groq import GroqActionClient

        return GroqActionClient(
            api_key=api_key, timeout_seconds=timeout, min_interval_seconds=interval
        )
    if provider == "openrouter":
        from engine.openrouter import OpenRouterActionClient

        return OpenRouterActionClient(
            api_key=api_key, timeout_seconds=timeout, min_interval_seconds=interval
        )
    if provider == "gemini":
        from engine.gemini import GoogleGeminiActionClient

        return GoogleGeminiActionClient.from_api_key(
            api_key, timeout_seconds=timeout, min_interval_seconds=interval
        )
    if provider == "ollama":
        from engine.ollama import OllamaActionClient

        base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        return OllamaActionClient(base_url=base_url, timeout_seconds=max(timeout, 120))
    return None


def _planner(journey: JourneyFileV1, provider: str, model: str, api_key: str):
    plan = {
        "kind": "fixture_plan.v1",
        "actions": [step.model_dump(exclude_none=True) for step in journey.plan],
        "synthetic_values": journey.type_values,
    }
    if provider == "scripted":
        if not journey.plan:
            raise RunConfigError("This journey has no scripted plan; choose an AI provider.")
        config = {"planner": plan}
    else:
        live: dict[str, Any] = {"kind": f"{provider}.v1", "synthetic_values": journey.type_values}
        if journey.plan:
            live["fallback"] = plan
        else:
            live["allow_no_fallback"] = True
        config = {"planner": live}
    client = _client(provider, api_key) if provider != "scripted" else None
    return planner_from_config(
        config,
        **({f"{provider}_client": client, f"{provider}_model": model} if client else {}),
        max_calls=int(os.environ.get("PLANNER_MAX_CALLS_PER_RUN", "40")),
        max_quota_retries=1,
        quota_backoff_seconds=float(os.environ.get("PLANNER_429_BACKOFF_SECONDS", "30")),
        max_transient_retries=3,
        transient_backoff_seconds=10,
        max_invalid_retries=3,
    )


def _target_policy(journey: JourneyFileV1, origin: str, origins: list[str]) -> dict[str, Any]:
    if journey.target_policy:
        text = json.dumps(journey.target_policy).replace("{fixture_base_url}", origin)
        return json.loads(text)
    policy: dict[str, Any] = {
        "navigation_origins": origins,
        "resource_origins": origins,
        "navigation_path_prefixes": ["/"],
        # A live site loads assets from CDNs; a local site folder serves everything itself.
        "allow_any_resource_origin": not journey.site_dir,
        "max_actions": journey.max_steps,
        "no_progress_limit": 6,
        "total_timeout_ms": 900_000,
        "user_agent": USER_AGENT,
    }
    if journey.staging_writes:
        policy["allowed_methods"] = ["GET", "HEAD", "OPTIONS", "POST"]
        policy["write_origins"] = [origins[0]]
        policy["max_writes"] = 5
    return policy


def run_journey(
    journey: JourneyFileV1,
    *,
    base_dir: Path,
    provider: str = "scripted",
    model: str = "",
    api_key: str = "",
    out_dir: Path | None = None,
    repo_dir: Path | None = None,
    headless: bool = True,
    browser_executable: str | None = None,
    axe_path: Path | None = None,
    session_state: dict[str, Any] | None = None,
) -> RunOutput:
    if provider not in PROVIDERS:
        raise RunConfigError(f"Unknown provider {provider!r}; use one of {', '.join(PROVIDERS)}.")
    if provider in KEY_ENV and not api_key:
        api_key = os.environ.get(KEY_ENV[provider], "")
        if not api_key:
            raise RunConfigError(f"Set {KEY_ENV[provider]} (or pass --api-key-env) for {provider}.")
    model = model or os.environ.get(MODEL_ENV.get(provider, ""), "")
    if provider not in {"scripted"} and not model:
        raise RunConfigError(f"Choose a model for {provider} with --model.")
    rule_set = resolve_rules(journey.rules or {})
    steps: list[StepEvidenceV1] = []
    run_id = uuid4()
    artifacts = (out_dir or Path(".")) / "artifacts"
    axe_source = axe_path.read_text(encoding="utf-8") if axe_path and axe_path.is_file() else None
    with _site(journey, base_dir) as origin:
        start_url = f"{origin}{journey.start_path}" if journey.site_dir else str(journey.start_url)
        origins_for_session = [origin]
        origins = [
            item.replace("{fixture_base_url}", origin).rstrip("/")
            for item in journey.allowed_origins
        ] or [origin]
        if session_state is not None:
            # A saved sign-in is cut down to this journey's own sites before use.
            session_state = limit_to_origins(session_state, origins + origins_for_session)
        executor = KeyboardExecutor(
            run_id=run_id,
            start_url=start_url,
            allowed_origins=origins,
            target_policy=_target_policy(journey, origin, origins),
            completion_policy=journey.completion(),
            barrier_check=journey.barrier_check,
            max_steps=journey.max_steps,
            action_timeout_ms=int(os.environ.get("EVALUATOR_ACTION_TIMEOUT_MS", "5000")),
            headless=headless,
            browser_executable_path=browser_executable,
            artifact_store=LocalArtifactStore(artifacts, run_id),
            on_step=lambda evidence, stored: steps.append(evidence),
            rule_set=rule_set,
            axe_source=axe_source,
            session_state=session_state,
        )
        planner = _planner(journey, provider, model, api_key)
        result = executor.run_with_planner(planner, goal=journey.goal)
    output = RunOutput(
        journey=journey,
        provider=provider,
        model=model,
        start_url=start_url,
        result=result,
        rule_set=rule_set,
        steps=steps,
        artifacts_dir=artifacts,
        planner_metadata=_safe_metadata(planner.runtime_metadata(), api_key),
    )
    if repo_dir is not None:
        output.locations = map_to_code(result, repo_dir)
    return output


def _safe_metadata(metadata: dict[str, Any], api_key: str) -> dict[str, Any]:
    text = json.dumps(metadata, default=str)
    if api_key:
        text = text.replace(api_key, "[redacted]")
    return json.loads(text)


def map_to_code(result: EvaluationResult, repo_dir: Path) -> dict[str, dict[str, Any]]:
    """Where to fix each finding in a local checkout (rule-based; nothing is sent anywhere)."""
    index = build_index(repo_dir).to_json()
    patterns = {rule.id: rule.code_patterns for rule in load_catalog().rules}
    locations = {}
    for finding in result.findings:
        located = locate(
            finding.model_dump(mode="json"),
            index,
            repo_dir,
            rule_patterns=patterns.get(finding.rule_id, []),
        )
        locations[finding.id] = located.to_dict()
    return locations


def scan_page(
    *,
    base_dir: Path,
    site_dir: str | None = None,
    path: str = "/",
    url: str | None = None,
    rules: dict[str, Any] | None = None,
    headless: bool = True,
    out_dir: Path | None = None,
) -> EvaluationResult:
    """Run the page checks on one page without a journey (no key presses, no AI).

    Static checks become "needs review"; the Tab walk can still confirm problems such as
    focus that changes the page or a missing skip link.
    """
    journey = JourneyFileV1(
        name="Page check",
        goal="Check one page for keyboard accessibility problems.",
        start_url=url,
        site_dir=site_dir,
        start_path=path,
        success={"url_contains": "/__accesspath-never__"},
        rules=rules or {},
        max_steps=1,
    )
    run_id = uuid4()
    with _site(journey, base_dir) as origin:
        start_url = f"{origin}{journey.start_path}" if journey.site_dir else str(journey.start_url)
        executor = KeyboardExecutor(
            run_id=run_id,
            start_url=start_url,
            allowed_origins=[origin],
            target_policy=_target_policy(journey, origin, [origin]),
            completion_policy=journey.completion(),
            barrier_check=None,
            max_steps=1,
            action_timeout_ms=5000,
            headless=headless,
            artifact_store=LocalArtifactStore(out_dir or Path(".accesspath") / "scan", run_id),
            on_step=lambda evidence, stored: None,
            rule_set=resolve_rules(journey.rules),
        )
        return executor.run([])
