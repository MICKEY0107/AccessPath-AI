# AccessPath AI — Project Handoff

**Updated:** 25 October 2026 (end of day)
**Read this first in a new chat.** It is the single source of truth for where the project stands.

## 1. What the project is

AccessPath AI checks whether a person using only a keyboard can finish a real task on a website. A live LLM planner proposes one keyboard action at a time (Tab, Shift+Tab, Enter, Space, arrows, Escape, or Type a permitted value). A deterministic policy approves each action before Playwright presses the key. Every step is saved with focus evidence and before/after screenshots, and the run ends in an evidence-backed outcome: completed, blocked, inconclusive, agent error, safety stopped, or environment blocked.

It is a 5-credit college project. First users are **developers and product managers**.

## 2. Decisions the owner has made (do not re-ask)

- **Free model tiers only:** Gemini, OpenRouter and Groq. No paid APIs.
- **AI only:** demo journeys run with a live planner and no deterministic or scripted steps.
- **Local only:** commit on the local branch. **Do not push and do not open PRs** until the owner asks.
- **Never touch `C:\code\RepoPilot`** (a separate project).
- Plan doc (goal, phases, gates, risks): https://claude.ai/artifact/HkebUHk6XuC9GTY29r9XQm

## 3. Git state

- Work happens on the local branch `claude/project-thread-w787he`.
- PR #1 (https://github.com/MICKEY0107/AccessPath-AI/pull/1) contains **only the first commit** (per-run provider/model/key picker). Later commits are local and unpushed.
- Git reports "dubious ownership". Use this per command instead of changing global config:
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='C:/code/AccessPath AI' git …`
- `gh` is not installed.

Local commits, oldest first:

| Commit | What it did |
|---|---|
| Per-run picker | Pick provider, type an API key, choose the model per run. Keys are Fernet-encrypted (keyed from `DJANGO_SECRET_KEY`, 1 h TTL), passed to the worker as ciphertext, never stored, scrubbed from evidence and errors, shown masked (`••••abcd`) |
| Resilient planning + real websites | Bad answers retried (`PLANNER_MAX_INVALID_RETRIES`, default 3); Retry-After honoured; provider error text saved and shown; Groq no longer mislabelled as Gemini; "Evaluate a real website" form (read-only policy, public hosts only, success checks `url_contains` / `text_present`) |
| UI redesign | Lavender backdrop, white app frame, tabs, workspace layout (start tiles, searchable journeys, recent runs, guide panel), add-website dialog, wide layout, phone layout |
| AI-only demo journeys | Two demo journeys, halved observation size, Groq strict structured outputs, typed-values memory, policy rule `COMMIT_TYPED_VALUE_FIRST` |

## 4. Demo journeys (both pass live, AI only)

Seeded from `fixtures/public/journey-manifest.json` (manifest `public-pilot-1.1.0`) by `seed_public_journeys`. Both have `allow_no_fallback: true`, so a provider failure ends the run as an agent error with the provider's reason.

| Journey | Start | Success check | Last live result |
|---|---|---|---|
| Demo (simple) — Wikipedia article search | `https://en.wikipedia.org/wiki/Main_Page` | address contains `/wiki/Web_accessibility` | Completed in 8 steps on Groq `openai/gpt-oss-20b` |
| Demo (complex) — TodoMVC add and complete to-dos | `https://todomvc.com/examples/react/dist/` (app from the public tastejs/todomvc repo) | page shows "Buy milk", "Call the clinic" and "1 item left" | Completed in 7 steps on Groq `openai/gpt-oss-120b` |

Real finding for demos: TodoMVC's per-item checkboxes have no accessible name.

**Free-tier limits to know:** Groq caps each model per minute (8,000 tokens for gpt-oss-20b) and per day (200,000 tokens). When a model's daily cap is hit, pick another model in the run form (for example `openai/gpt-oss-120b`). `openrouter/free` routes each call to a random model and is unreliable; the form warns about it.

## 5. Run it locally

```powershell
docker compose -f docker-compose.yml -f <override> up -d      # see the port note
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fixture_journeys
docker compose exec web python manage.py seed_public_journeys
```

- **Port:** another local app holds 127.0.0.1:8000. Map web to 8010 with an override file containing
  `services: { web: { ports: !override ["127.0.0.1:8010:8000"] } }`, then open http://127.0.0.1:8010/runs/.
- After engine changes, restart the worker: `docker compose restart worker` (Celery does not auto-reload).
- `.env` holds `GEMINI_*`, `OPENROUTER_*`, `GROQ_*` keys and models. Never print or commit it.
- **Tests:** run the full suite inside the container (the host has no Playwright browsers):
  `docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q` → **112 passed, 9 skipped** (live-site tests are opt-in).
- Host checks: `UV_CACHE_DIR=.uv-cache uv run ruff check .` (the cache variable avoids "Access is denied").
- On Windows, Python `read_text()`/`write_text()` default to cp1252; always pass `encoding="utf-8"`.

## 6. Where the code is

- `engine/` — framework-free core: `executor.py` (keyboard loop, observation, completion signals), `planner.py` (providers, retries, fallback or stop), `gemini.py` (system prompt), `groq.py`, `openrouter.py`, `provider_http.py` (error text, Retry-After), `policy.py`, `target_policy.py` (request rules, private-host block), `contracts.py` (Pydantic schemas).
- `apps/runs/` — views, service (`execute_configured_run`), Celery task, `credentials.py` (key sealing and scrubbing).
- `apps/journeys/real_sites.py` — the add-website form and public-host check.
- `templates/` — `base.html` (theme), `runs/list.html`, `runs/detail.html`, `core/home.html`.

## 7. What is next (Phase 1 of the plan doc)

1. **Confirm before blaming:** re-check a suspected barrier deterministically before reporting it, so planner mistakes are never reported as site barriers.
2. **Map findings to WCAG** (2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11, 3.2.1) with severity.
3. **Add checks:** focus visible, focus not obscured, skip link, focus order; flag unnamed controls (like TodoMVC's checkboxes).
4. **Run axe-core** on each new page state.
5. **Grow the benchmark** from the two demo journeys to about 10, measured on free tiers.

Gate 1 targets: 80% of live runs end in a trustworthy outcome and 90% of reported barriers are confirmed real.

Later ideas (not started): a VS Code assistant on top of a future CLI, and a voice-driven Chrome extension (research only).
