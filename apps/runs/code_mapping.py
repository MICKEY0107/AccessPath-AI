"""Attach code locations and fixes to a run's findings, using the journey's repository."""

from __future__ import annotations

from django.conf import settings

from apps.codebase.models import RepoStatus
from engine.code_index import load_index
from engine.code_locator import locate
from engine.code_safety import code_safety
from engine.locator_ai import LocatorChat, make_ai_search
from engine.rules import load_catalog

from .credentials import scrub
from .models import PlannerProvider, Run

MAX_AI_FINDINGS = 3
CHAT_URLS = {
    PlannerProvider.GROQ: "https://api.groq.com/openai/v1/chat/completions",
    PlannerProvider.OPENROUTER: "https://openrouter.ai/api/v1/chat/completions",
}


def ai_chat_for(run: Run, api_key: str) -> tuple[LocatorChat | None, str]:
    """An AI search client when the run's provider may read private code, else a reason."""
    if not settings.CODE_LOCATOR_USE_AI:
        return None, "AI search is turned off on this server."
    provider, model = run.planner_provider, run.planner_model
    if provider == PlannerProvider.FIXTURE or not model:
        return None, "No AI provider was used for this run."
    safety = code_safety(provider, model, settings.CODE_SAFE_PROVIDERS)
    if not safety.safe:
        return None, f"AI search skipped: {safety.reason}"
    if provider == PlannerProvider.OLLAMA:
        if not settings.OLLAMA_BASE_URL:
            return None, "Ollama is not configured."
        url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/chat"
        return LocatorChat(kind="ollama", url=url, model=model, timeout_seconds=120), ""
    if provider not in CHAT_URLS or not api_key:
        return None, "AI search needs the provider's API key."
    return LocatorChat(kind="openai", url=CHAT_URLS[provider], model=model, api_key=api_key), ""


def map_run_findings(run: Run, *, api_key: str = "", use_ai: bool = True) -> int:
    """Locate every finding of ``run`` in its journey's repository; returns how many mapped."""
    binding = run.journey.repo_binding
    if binding is None or binding.status != RepoStatus.READY or not binding.index_path.is_file():
        return 0
    index = load_index(binding.index_path)
    patterns = {rule.id: rule.code_patterns for rule in load_catalog().rules}
    chat, ai_note = ai_chat_for(run, api_key) if use_ai else (None, "")
    ai_search = make_ai_search(chat) if chat else None
    mapped = ai_calls = 0
    for finding in run.findings.all():
        data = dict(finding.data or {})
        search = ai_search if ai_calls < MAX_AI_FINDINGS else None
        result = locate(
            data,
            index,
            binding.source_dir,
            rule_patterns=patterns.get(finding.rule_id, []),
            ai_search=search,
        )
        if result.ai_used or (search and not result.exact):
            ai_calls += 1
        locations = result.to_dict()
        if ai_note and not result.exact and not result.ai_used:
            locations["notes"].append(ai_note)
        locations.update(
            {"repo": binding.short_name, "commit": binding.commit_sha, "binding_id": binding.pk}
        )
        previous = data.get("locations") or {}
        if previous.get("verification") and previous.get("fix") == locations.get("fix"):
            locations["verification"] = previous["verification"]
        data["locations"] = scrub(locations, [api_key])
        finding.data = data
        finding.save(update_fields=["data"])
        mapped += 1
    return mapped
