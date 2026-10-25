# AccessPath AI — Project Handoff

**Updated:** 26 October 2026, about 05:30 IST (after the overnight session of 25–26 October)
**Read this first in a new chat.** It is the single source of truth for where the project stands. Times in this file are IST unless marked UTC; the app's database stores UTC (IST = UTC + 5:30).

## 1. What the project is

AccessPath AI checks whether a person using only a keyboard can finish a real task on a website. A live LLM planner proposes one keyboard action at a time (Tab, Shift+Tab, Enter, Space, arrows, Escape, or Type a permitted value). A deterministic policy approves each action before Playwright presses the key. Every step is saved with focus evidence and before/after screenshots, and the run ends in an evidence-backed outcome: completed, blocked, inconclusive, agent error, safety stopped, or environment blocked.

It is a 5-credit college project (three-member team per the progress log). First users are **developers and product managers**. Goal statement (from the plan doc): run a declared task on a live site keyboard-only and return a verdict a developer or PM can act on — completed, or blocked at a named step with the WCAG criterion, a screenshot and a reproduction path.

Plan doc (goal, phases, gates, risks, sources): https://claude.ai/artifact/HkebUHk6XuC9GTY29r9XQm

## 2. Decisions the owner has made (do not re-ask)

| Decision | Why |
|---|---|
| Free model tiers only: Gemini, OpenRouter, Groq | College project; no paid API access. The owner has Antigravity Pro and free tiers only |
| AI only: demo journeys use a live planner, no deterministic or scripted steps | The point of the demo is AI planning on live or public-repo sites |
| Demo journeys: one simple, one complex, easy to understand | Owner had no specific sites in mind; asked for one of each |
| First users: developers and product managers | Owner's answer on 25 Oct |
| Local only: commit on the local branch; no pushes and no PRs until asked | Owner said "don't create a PR, change everything locally first" (after the picker branch had already been pushed). Owner then opened PR #1 themselves |
| Never touch `C:\code\RepoPilot` (CodeImpact) | Separate project. A session was opened there by mistake and stopped before it changed anything |
| Priority is the keyboard tool working like an industrial tool on actual sites | Owner's stated first priority; side ideas come later |
| The owner is moving to a separate local chat | To use their plan limits instead of Projects credit |

## 3. Open questions waiting for the owner

- **Repository visibility:** `MICKEY0107/AccessPath-AI` is public. This was flagged; no answer yet.
- **Mentor check:** must the course evidence be Gemini-only, or is any one provider acceptable? Unconfirmed.
- **Benchmark:** which further sites and journeys to add beyond the two demos (owner has none in mind).
- **When to push** the local commits and update PR #1.

## 4. Git state

- Local branch `claude/project-thread-w787he` tracks `origin/claude/project-thread-w787he` and is ahead of it by every commit after `1a20c1b`. `main` is still the initial commit `d4c5299`.
- PR #1 (https://github.com/MICKEY0107/AccessPath-AI/pull/1) contains **only `1a20c1b`** (the per-run picker).
- `apps/runs/tasks.py` sometimes shows as modified with only line-ending differences (CRLF on disk, LF in git). Do not commit it; `git checkout -- apps/runs/tasks.py` clears it.
- Git reports "dubious ownership" (`.git` is owned by `CodexSandboxOffline`). Use per command, not a global config change:
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='C:/code/AccessPath AI' git …`
- `gh` is not installed.

| Commit | Time (IST) | What it did |
|---|---|---|
| `d4c5299` Initial commit | 25 Oct, 23:38 | Phase 1 vertical slice plus the folder cleanup done by the first cloud session: plans moved to `docs/planning`, the 28 Sep handoff and original synopsis moved to `docs/archive`, Groq probes became `scripts/check_groq*.py`, Ruff E501 ignored for the report builders. Pushed to `main` |
| `1a20c1b` Per-run picker (pushed, PR #1) | 26 Oct, 00:46 | Provider, API key and model chosen per run; keys Fernet-encrypted (keyed from `DJANGO_SECRET_KEY`, 1 h TTL), passed to the worker as ciphertext, never stored, scrubbed from evidence and errors, shown masked (`••••abcd`) |
| `fdf7cf8` Resilient planning + real websites | 01:37 | Retries for bad answers, Retry-After waits, provider error text recorded and shown, Groq no longer labelled as Gemini, "Evaluate a real website" form |
| `c79fb84`, `6afc208` UI redesign | 02:21, 02:33 | Theme after the owner's reference image; wide layout |
| `c0bd434` AI-only demo journeys | 04:41 | Two demo journeys, smaller observations, Groq strict outputs, typed-values memory, `COMMIT_TYPED_VALUE_FIRST` |
| `c0033cc` Handoff rewrite | 05:05 | First version of this file; progress log entry 1.12 |

## 5. Ideas and features register

| Item | Status | Notes and reason |
|---|---|---|
| Per-run provider, API key and model picker | Done | Env keys remain the fallback |
| Encrypt user keys; never store or log them | Done | Fernet ciphertext in the Celery task args only |
| Retry bad answers before falling back | Done | `PLANNER_MAX_INVALID_RETRIES`, default 3 |
| Honour Retry-After and "try again in Ns" hints | Done | Up to 3 patient retries; wait capped at 120 s |
| Raise answer limits | Done | OpenRouter 2048, Gemini 1024; Groq kept at 1024 because `max_tokens` counts toward its per-minute cap |
| Record and show the provider's real error | Done | Shown on the run page as "Why: …" |
| Warn when `openrouter/free` is chosen | Done | It routes each call to a random model |
| Show the model what it already did | Done | History carries the focused control after each step, the target hint and the typed value; observation lists all typed values |
| Real-website journeys from the dashboard | Done | Read-only (GET/HEAD/OPTIONS), site-bound navigation, public CDN subresources allowed, private and local hosts refused, no scripted fallback |
| UI redesign after the owner's reference | Done | Wide app frame on a lavender backdrop |
| AI-only demo journeys | Done | Both pass live (section 6) |
| Groq strict structured outputs | Done | For `openai/gpt-oss-*` models; others use JSON mode |
| Smaller observations | Done | Focused control, next 18 and previous 4 tab stops, 1,500 characters of text, defaults omitted |
| Cut planner cost further: prompt caching | Planned | Not done |
| Stop early when the model repeats actions | Planned | Not done; today only the focus-cycle detector (`no_progress_limit`) and the policy rule exist |
| Confirm a barrier deterministically before reporting it | Planned | Phase 1 item 1; most important for trust |
| Map findings to WCAG with severity | Planned | 2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11, 3.2.1 |
| Focus visible, focus obscured, skip link, focus order checks; unnamed controls | Planned | TodoMVC's unnamed checkboxes are a ready example |
| axe-core scan at each new page state | Planned | |
| Benchmark of about 10 journeys | Planned | Starts from the two demos |
| Staging writes, saved-session logins, CLI, CI gate, reports, baselines | Planned (Phase 2) | |
| VS Code developer assistant | Planned (Phase 3) | Built on the future CLI |
| Chrome voice extension for motor-disabled users | Postponed (research only) | Acts with the user's own accounts, so it needs a different trust model and user research; OS voice control already exists |
| Paid default model for benchmarks | Dropped | Owner has free tiers only |
| Deterministic fixture fallback in demo journeys | Dropped for demos | Owner wants AI only; the clinic fixtures still keep their scripted fallback |
| Opening a new PR | Dropped for now | Owner asked for local-only work |

## 6. Live run results

Times are from the run records (UTC) with IST in brackets.

| Run | Journey | Model | Steps | Outcome | Lesson |
|---|---|---|---|---|---|
| `842fdbbe` 19:13 UTC (00:43) | Clinic accessible | Groq `llama-3.1-8b-instant` with a fake demo key | 21 | Completed via scripted fallback (`GROQ_UNAVAILABLE`) | Typed keys are used and masked; key never appeared in DB, logs or Redis |
| `ca286114` 19:18 UTC (00:48) | Clinic accessible | OpenRouter `openrouter/free` (owner's key) | 22 | Completed via fallback (`OPENROUTER_UNAVAILABLE`) | Prompted the fallback investigation |
| Probe, ~00:55 | 12 calls to `openrouter/free` | | | 4 of 12 usable | Failures: reasoning models ran out of tokens, 404 "no endpoint supports these parameters", 502s |
| Probe, ~00:58 | 6 calls to Groq `openai/gpt-oss-20b` | | | 6 of 6 usable | |
| `92890861` 19:40 UTC (01:10) | Wikipedia (dashboard-added real site) | Groq `gpt-oss-20b` | 11 | Agent error, `GROQ_QUOTA_FAILURE` | 2048 `max_tokens` used up Groq's 8,000 tokens per minute; reverted to 1024 and added Retry-After waits |
| `63831eb0` 19:50 UTC (01:20) | Wikipedia (dashboard-added real site) | Groq `gpt-oss-20b` | **6** | Completed, no fallback | First live real-site pass; 6 rate-limit waits absorbed |
| `08e3afde` 22:24 UTC (03:54) | Demo (simple) Wikipedia | Groq `gpt-oss-20b` | **8** | Completed, no fallback, no rate-limit hits | Smaller observations removed the rate limiting. The 6-step and 8-step figures are two different runs; both are correct |
| `c465af7d` 22:24 UTC | Demo (complex) TodoMVC | Groq `gpt-oss-20b` | 4 | Agent error, Groq 400 "Failed to validate JSON" | Model typed but never pressed Enter; prompt said "Tab after typing" |
| `c510c273` 22:28 UTC | TodoMVC | Groq `gpt-oss-20b` | 26 | Agent error, Groq 400 | Added items but repeated "Buy milk"; long Tab tour through the page footer |
| `16e7a3d4` 22:57 UTC | TodoMVC | Groq `gpt-oss-20b` | 10 | Agent error, Groq 400 (10 of 20 calls invalid) | Typed twice without Enter, overwriting "Buy milk"; led to strict outputs and the policy rule |
| `01bab2d1` 23:04 UTC | TodoMVC | Groq `gpt-oss-20b` | 2 | Agent error, `GROQ_QUOTA_FAILURE` (daily cap) | gpt-oss-20b hit 200,000 tokens per day |
| `3fea7ef5` 23:08 UTC (04:38) | Demo (complex) TodoMVC | Groq `openai/gpt-oss-120b` | **7** | Completed, no fallback, 0 invalid answers | Type, Enter, Type, Enter, Tab, Tab, Space |

## 7. Known bugs, flaky behaviour and surprises

- **Groq JSON mode is flaky with gpt-oss:** frequent 400 "Failed to validate JSON". At temperature 0 a retry repeats the same failure. Fixed by strict structured outputs (gpt-oss only) and temperature 0.4 on retries. Other Groq models still use JSON mode.
- **Groq limits:** 8,000 tokens per minute and 200,000 tokens per day per model on the free tier (observed for gpt-oss-20b). `max_tokens` counts toward the minute cap. Switch model when the daily cap is hit.
- **The Groq 429 message includes the organisation id** (`org_…`); it is saved in local run evidence. Not a secret, but visible.
- **`openrouter/free` is unreliable** for multi-step runs (4 of 12 usable in the probe).
- **Gemini:** an earlier run (`2cba2868`, 28 Sep) fell back with `GEMINI_TIMEOUT`. Gemini has not been retested since today's changes (unconfirmed whether it now passes the demos).
- **Prompt wording matters:** "after typing, press Tab" broke add-item fields; the prompt now says to press Enter in search or add-item fields.
- **TodoMVC:** the new-todo input is focused on load; the first Tab from the top goes to an `http://todomvc.com` link (a different origin from the `https` start, so following it is a safety stop). Per-item checkboxes have no accessible name. The page posts analytics, which policy blocks without stopping the run.
- **Wikipedia:** posts telemetry (`/ins-502b/v2/events`, `intake-analytics.wikimedia.org`); blocked as non-fatal policy events.
- **GOV.UK** was probed (cookie banner first, then skip link, search at the 7th–8th Tab) but not used: search results need many Tabs, which is slow on free tiers.
- **Steps are saved only when a run ends**, so the run page shows no steps while running.
- **Worker does not reload code:** restart it after engine changes.
- **Environment:** port 8000 is taken by another local app (`orchestrator_api` uvicorn from a Codex runtime); `uv` needs `UV_CACHE_DIR=.uv-cache`; the host has no Playwright browsers (11 browser tests fail on the host, pass in the container); Python file I/O defaults to cp1252 on this machine. Docker was down at the start of 25 Oct and is now running.

## 8. What I was in the middle of, and the exact next step

Nothing is half-done in code: all work is committed and 112 tests pass. The last finished task was this handoff.

**Exact next step:** Phase 1 item 1, "confirm before blaming". When a run would end as `blocked` or `agent_error` on a real site, re-check deterministically: re-focus the target control named by the planner's last `target_hint`, test whether it is focusable with Tab and whether Enter or Space activates it, and report a barrier only when that check confirms it; otherwise report an agent failure. Start in `engine/executor.py` around `_execute_actions` (the terminal branches) and add tests in `tests/test_browser_fixture_flow.py` using the broken clinic fixture.

## 9. Run it locally

```powershell
docker compose -f docker-compose.yml -f <override> up -d      # see the port note
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fixture_journeys
docker compose exec web python manage.py seed_public_journeys
```

- **Port:** map web to 8010 with an override file containing
  `services: { web: { ports: !override ["127.0.0.1:8010:8000"] } }`, then open http://127.0.0.1:8010/runs/.
- Restart the worker after engine changes: `docker compose restart worker`.
- `.env` holds `GEMINI_*`, `OPENROUTER_*`, `GROQ_*` keys and models (currently `models/gemini-3.5-flash-lite`, `openrouter/free`, `openai/gpt-oss-20b`). Never print or commit it.
- **Tests (in the container):** `docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q` → **112 passed, 9 skipped** (live-site tests are opt-in).
- Host lint: `UV_CACHE_DIR=.uv-cache uv run ruff check .`

## 10. Where the code is

- `engine/` — `executor.py` (keyboard loop, observation, completion signals including `url_contains` and `text_present`), `planner.py` (providers, retries, fallback or stop), `gemini.py` (system prompt), `groq.py` (strict schema), `openrouter.py`, `provider_http.py` (error text, Retry-After), `policy.py` (`COMMIT_TYPED_VALUE_FIRST`), `target_policy.py` (request rules, private-host block), `contracts.py`.
- `apps/runs/` — views, `services.py` (`execute_configured_run`), `tasks.py`, `credentials.py`.
- `apps/journeys/real_sites.py` — add-website form and public-host check.
- `fixtures/public/journey-manifest.json` — demo journeys (`demo-simple-wikipedia-search`, `demo-complex-todomvc`) and the older reviewed pilots.
- `templates/` — `base.html` (theme), `runs/list.html`, `runs/detail.html`, `core/home.html`.

## 11. What is next

**Phase 1 (from the plan doc):**

1. Confirm before blaming (section 8).
2. Map findings to WCAG with severity.
3. Add focus visible, focus obscured, skip link and focus order checks; flag unnamed controls.
4. Run axe-core on each new page state.
5. Cut planner cost further: prompt caching, and stop early when the model repeats actions.
6. Grow the benchmark from the two demos to about 10 journeys on free tiers.

Gate 1 targets: 80% of live runs end in a trustworthy outcome; 90% of reported barriers confirmed real.

**Open course items:** confirm with the mentor whether evidence must be Gemini-only; the final 3 accessible + 5 broken clinic runs on one provider; the write-up; the second-person review; the release tag.
