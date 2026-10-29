# AccessPath AI — Improvements Backlog

Collected on 26 October 2026 (IST) from the project thread of 25–26 October, plus items the project coordinator reported from the project chat (marked "from project chat"). Commit hashes refer to the local branch `claude/project-thread-w787he`. Anything not verified is marked **unconfirmed**.

Status keys: **done** · **partly done** · **agreed, not started** · **postponed** · **rejected** · **no reply**.

## Web product plan (agreed 29 October 2026)

The product is web only. Stage numbers refer to section 11 of `PROJECT_HANDOFF.md` and the plan doc. All items below are **agreed, not started**.

| Item | Stage | Notes |
|---|---|---|
| Rules catalog (`rules/catalog.json`) with WCAG/ACT sources and presets Essential, WCAG 2.2 AA, Strict | 1 | Shipped with the code, reviewed and versioned; never fetched at run time |
| Rules settings page: toggles, disable with reason, ignores with an expiry date, custom rules from a fixed set of checks | 1 | No arbitrary code in rule config |
| `Finding` type and table; confirm before blaming | 2 | Site barrier vs agent failure |
| Report shows each rule as passed, failed, not applicable or needs a human | 3-4 | A pass never means "not checked" |
| Accessibility report page in CodeImpact's structure, with an "In plain words" panel for PMs | 4 | Label says whether the text is rule-based or AI |
| Sign-in for the web app | 5 | Needed before storing repos or keys |
| Active codebase panel: repo URL, branch, one-time token, live site URL, Clone & analyze, recent repos, Remove clone | 5 | Modelled on CodeImpact's repo binding screen |
| Secure clone and front-end index | 5 | Shallow, read-only, never run; symlink, size and blocked-path checks; secret scan |
| Model settings upgrade: List models, Save & use, Forget key, opt-in encrypted remembered keys | 5 | Decided 29 Oct |
| Local Ollama provider | 5 | Decided 29 Oct |
| Code-safety badge per provider | 5 | Gemini free tier and `openrouter/free` blocked from private code ([Gemini terms](https://ai.google.dev/terms): do not submit confidential information to unpaid services) |
| Where to fix: Exact match, Likely cause, Also affected; fixes with patches and Re-run | 6 | Patches never applied to the user's repo |
| Verify a fix on the clinic fixture | 6 | First thing to cut if time is short |
| Use CodeImpact (`C:\code\RepoPilot`) as a read-only reference for cloning and code mapping | 5-6 | Waiting for the folder to be connected or files attached |
| CLI, MCP server, CI with SARIF and PR comments, record-and-replay | Future | Replaces the VS Code assistant idea |

## Planner and models

### Per-run provider, API key and model picker
- **What:** For a live provider, the run form takes an optional model id and API key; blank fields fall back to `GEMINI_*`, `OPENROUTER_*`, `GROQ_*` in `.env`.
- **Why:** You asked to choose provider, key and model per run instead of a fixed model.
- **Status:** done (`1a20c1b`, the only commit in PR #1).
- **Code:** `apps/runs/views.py`, `apps/runs/services.py`, `apps/runs/tasks.py`, `templates/runs/list.html`.
- **Effort:** medium.
- **Detail:** Model ids must match `^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$`, max 255 chars; keys max 512, no spaces.

### Encrypted, never-stored user API keys
- **What:** Typed key is sealed with Fernet (key derived from `DJANGO_SECRET_KEY`, 1-hour TTL), sent to the worker only as ciphertext in the Celery task args, used in memory, scrubbed from evidence, metadata, `error_detail` and re-raised errors; run page shows only `••••` + last 4.
- **Why:** The coordinator's brief required keys not to be stored or logged in plain form.
- **Status:** done (`1a20c1b`).
- **Code:** `apps/runs/credentials.py`, `apps/runs/tasks.py`, `apps/runs/services.py`, `templates/runs/detail.html`.
- **Effort:** medium.
- **Detail:** Verified with a fake key `demo-invalid-key-0000ABCD`: absent from DB row, step evidence, web/worker logs and Redis. `start_run` uses `sensitive_post_parameters("api_key")`. Expired or tampered token → run fails `environment_blocked` / `RUN_CREDENTIAL_UNAVAILABLE`.

### Retry one-off bad answers before falling back
- **What:** Empty or truncated completions, unroutable OpenRouter picks, Groq JSON failures and schema mismatches are retried before the run gives up.
- **Why:** Most runs fell back to the scripted plan after a single failure; a 12-call probe of `openrouter/free` gave only 4 usable answers.
- **Status:** done (`fdf7cf8`; default raised from 2 to 3 in `c0bd434`).
- **Code:** `engine/planner.py` (`GeminiPlanner.propose_next_action`, `_request_action`), `config/settings/base.py` (`PLANNER_MAX_INVALID_RETRIES`).
- **Effort:** small.
- **Detail:** Bad keys (401/403 → `*_AUTH_FAILED`) and unknown models (Groq 404 → `GROQ_MODEL_NOT_FOUND`) fail at once.

### Honour Retry-After and "try again in Ns" hints
- **What:** On 429, wait the provider's `Retry-After` header or the "try again in 9.3s" text + 1 s, capped at 120 s, with at least 3 retries when a hint exists.
- **Why:** The first live Wikipedia run (`92890861`) died on Groq's 8,000 tokens-per-minute limit after 11 steps.
- **Status:** done (`fdf7cf8`).
- **Code:** `engine/provider_http.py` (`retry_after_seconds`), `engine/planner.py` (`_quota_wait_seconds`, `_quota_retry_budget`).
- **Effort:** small.
- **Detail:** Minute-form hints like "7m50.88s" (daily cap) are not parsed; the run stops, which is correct for daily caps.

### Answer-length limits
- **What:** OpenRouter `max_tokens` 768 → 2048; Gemini `max_output_tokens` 256 → 1024; Groq kept at 1024.
- **Why:** Reasoning models on `openrouter/free` ran out of tokens before writing the JSON (`finish_reason='length'`).
- **Status:** done (`fdf7cf8`).
- **Code:** `engine/openrouter.py`, `engine/gemini.py`, `engine/groq.py`.
- **Effort:** small.
- **Detail:** Raising Groq to 2048 caused rate limiting, because Groq counts `max_tokens` toward its per-minute cap (requests showed "Requested 5322"). Reverted.

### Record and show the provider's real error
- **What:** Provider message and HTTP status are kept (key redacted) in `last_error` and `fallback_detail`, shown on the run page as "Why: …"; a contentless completion says "the model ran out of output tokens".
- **Why:** Runs only showed `OPENROUTER_UNAVAILABLE`, which hid the cause.
- **Status:** done (`fdf7cf8`).
- **Code:** `engine/provider_http.py`, `engine/openrouter.py`, `engine/groq.py`, `engine/planner.py` (`ResilientPlanner`), `templates/runs/detail.html`.
- **Effort:** small.

### Stop labelling Groq failures as Gemini
- **What:** Each planner subclass carries its own error family, so a Groq failure reads `GROQ_UNAVAILABLE`.
- **Why:** Run `354aac8a` (28 Sep) showed `GEMINI_UNAVAILABLE` on a Groq run.
- **Status:** done (`fdf7cf8`).
- **Code:** `engine/planner.py`.
- **Effort:** small.

### Pin a specific model instead of `openrouter/free`
- **What:** Use a fixed model id per provider; the form warns when `openrouter/free` or a `:free` id is chosen.
- **Why:** `openrouter/free` sends each call to a random free model. Probe: 4/12 usable; failures were token exhaustion (`nvidia/nemotron-3.5-super-vl:free`), 404 "No endpoints found that support the requested parameters", and 502s.
- **Status:** partly done (warning done in `fdf7cf8`; `.env` still sets `OPENROUTER_MODEL=openrouter/free`).
- **Code:** `templates/runs/list.html`, `.env` (not committed).
- **Effort:** small.

### Groq strict structured outputs
- **What:** For `openai/gpt-oss-*` models, send `response_format` `json_schema` with `strict: true` and a strict copy of the action schema; other Groq models keep JSON mode.
- **Why:** Groq JSON mode returned 400 "Failed to validate JSON" on up to half the calls (10 of 20 in run `16e7a3d4`).
- **Status:** done (`c0bd434`).
- **Code:** `engine/groq.py` (`STRICT_ACTION_SCHEMA`, `response_format_for`).
- **Effort:** small.
- **Detail:** After the change, run `3fea7ef5` had 0 invalid answers. Strict mode needs every property in `required`, nullable types for optional values, `additionalProperties: false`.

### Sample more freely when retrying a bad answer
- **What:** After a retryable failure, the next call uses temperature 0.4 instead of 0.
- **Why:** At temperature 0 a retry repeated the same malformed answer.
- **Status:** done (`c0bd434`).
- **Code:** `engine/groq.py`, `engine/openrouter.py` (`RETRY_TEMPERATURE`).
- **Effort:** small.

### Smaller planner observations
- **What:** Send the focused control, the next 18 and previous 4 tab stops, 1,500 characters of page text, and omit default-valued fields.
- **Why:** Each call was about 4,000–5,000 tokens, so free tiers throttled runs.
- **Status:** done (`c0bd434`).
- **Code:** `engine/executor.py` (`OBSERVATION_*` constants, `_planner_observation`), clients use `model_dump_json(exclude_defaults=True)`.
- **Effort:** small.
- **Detail:** The next Wikipedia run had no rate-limit hits. Unconfirmed exact token count after the change ("about half" is an estimate).

### Prompt caching
- **What:** Reuse the long system prompt across calls where the provider supports caching.
- **Why:** Further cuts token use on free tiers.
- **Status:** agreed, not started.
- **Code:** `engine/gemini.py`, `engine/groq.py`, `engine/openrouter.py`.
- **Effort:** medium. Unconfirmed which free tiers support caching.

### Stop early when the model repeats itself
- **What:** End or redirect a run when the planner proposes the same action on the same control several times without progress.
- **Why:** Run `e1106f6a` (28 Sep) used all 40 calls; run `c510c273` toured 18 Tabs through the TodoMVC footer.
- **Status:** agreed, not started (only the focus-cycle detector `no_progress_limit` and `COMMIT_TYPED_VALUE_FIRST` exist).
- **Code:** `engine/executor.py`, `engine/planner.py`.
- **Effort:** small.

### Show the model what it already did
- **What:** History entries carry `focus_after`, `target_hint` and `typed_value`; the observation lists every value typed so far; prompt explains cycling.
- **Why:** The model repeated "Buy milk" and lost track of items once history (8 entries) scrolled.
- **Status:** done (`fdf7cf8` for focus and hints; `c0bd434` for typed values).
- **Code:** `engine/contracts.py`, `engine/executor.py`, `engine/gemini.py`.
- **Effort:** small.

### Prompt: commit typed values correctly
- **What:** Prompt says press Enter in search and add-item fields, Tab in multi-field forms, Space for checkboxes, and never type twice in a row.
- **Why:** The old rule "after Type, propose Tab" made the model skip Enter in TodoMVC (run `c465af7d`).
- **Status:** done (`c0bd434`).
- **Code:** `engine/gemini.py` (`SYSTEM_INSTRUCTION`, shared by all providers).
- **Effort:** small.

### Retest Gemini and OpenRouter on the demo journeys
- **What:** Run both demos on Gemini (`models/gemini-3.5-flash-lite`) and a pinned OpenRouter model.
- **Why:** Only Groq has been tested since the fixes; the last Gemini run (`2cba2868`, 28 Sep) fell back with `GEMINI_TIMEOUT`.
- **Status:** no reply (not explicitly proposed before; recommended here).
- **Effort:** small.

### Groq tests and README coverage (from project chat)
- **What:** Add tests and README notes for the Groq client.
- **Why:** The first cloud session found Groq had no tests and no README mention.
- **Status:** partly done: Groq client tests now exist in `tests/test_planner_resilience.py`; README mentions Groq in the new sections. Unconfirmed whether a dedicated Groq setup section exists.
- **Effort:** small.

### Paid default model for benchmark runs
- **What:** Use a paid model for benchmark runs.
- **Status:** rejected (you have free tiers only).

## Policy and safety

### Read-only real-site policy
- **What:** Real-site journeys allow only GET/HEAD/OPTIONS, navigation limited to the site's own origins, no popups or downloads, public CDN subresources allowed (`allow_any_resource_origin`), private and local hosts blocked.
- **Why:** You asked for evaluations on actual sites; the existing pilot policy blocked CDN assets.
- **Status:** done (`fdf7cf8`).
- **Code:** `engine/contracts.py` (`TargetPolicyV1`), `engine/target_policy.py` (`is_local_or_private_host`).
- **Effort:** medium.
- **Detail:** Sign-in and checkout stop at the first POST by design.

### Public-host check for added websites
- **What:** Start URL and extra origins must resolve only to public IPs, checked at creation and again at run start, unless `ALLOW_PRIVATE_NETWORKS=true`.
- **Why:** Prevents the evaluator from opening internal network addresses.
- **Status:** done (`fdf7cf8`).
- **Code:** `apps/journeys/real_sites.py` (`host_is_public`), `apps/runs/services.py`.
- **Effort:** small.
- **Detail:** DNS rebinding between check and navigation is not fully prevented.

### Block re-typing before the value is committed
- **What:** Policy rejects a second Type into the same field until Enter or Tab (`COMMIT_TYPED_VALUE_FIRST`).
- **Why:** In run `16e7a3d4` the model typed "Call the clinic" over "Buy milk".
- **Status:** done (`c0bd434`).
- **Code:** `engine/policy.py`, `engine/executor.py`.
- **Effort:** small.
- **Detail:** Matches by the focused control's accessible name; two different unnamed fields both read "" and could be confused (edge case, untested).

### Staging-only writes with test data
- **What:** Allow POST only to allowlisted staging hosts, with test data from a fixture file.
- **Why:** Most keyboard barriers are in forms, sign-up and checkout.
- **Status:** postponed (Phase 2 of the plan).
- **Effort:** medium.

### Authenticated journeys via saved session state
- **What:** Upload a Playwright storage state per site; never type passwords.
- **Status:** postponed (Phase 2).
- **Effort:** medium.

## Checks and WCAG findings

### Confirm before blaming
- **What:** Before reporting a barrier, re-focus the target the planner was aiming for and test focusability and Enter/Space activation deterministically; otherwise report an agent failure.
- **Why:** A tool that blames the site for its own planner mistakes will not be trusted.
- **Status:** agreed, not started (exact next step in `PROJECT_HANDOFF.md`).
- **Code:** `engine/executor.py` (`_execute_actions` terminal branches), tests in `tests/test_browser_fixture_flow.py`.
- **Effort:** medium.

### Map findings to WCAG with severity
- **What:** Each finding names its criterion (2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11, 3.2.1; 2.4.13 advisory), severity, step and screenshot.
- **Status:** agreed, not started.
- **Effort:** medium.

### Focus visible, focus obscured, skip link, focus order checks
- **What:** Compare focused vs unfocused screenshots for an indicator, detect sticky elements covering focus, test the first Tab for a skip link, compare tab order with visual position.
- **Status:** agreed, not started.
- **Effort:** large.

### Flag unnamed controls
- **What:** Report focusable controls with no accessible name.
- **Why:** TodoMVC's per-item checkboxes have no accessible name (seen in every TodoMVC run).
- **Status:** agreed, not started (part of the checks item).
- **Effort:** small.

### axe-core at each new page state
- **What:** Run axe-core when the page changes and attach results.
- **Why:** Deque's report says automated rules catch 57.38% of issues; combining gives journey and page findings.
- **Status:** agreed, not started.
- **Effort:** medium.

## Evidence and reports

### Credential source and fallback reason on the run page
- **What:** Shows "Your API key (••••abcd)" or "Server API key", the model tried, and "Why: …".
- **Status:** done (`1a20c1b`, `fdf7cf8`).
- **Code:** `templates/runs/detail.html`.

### Save steps while the run is in progress
- **What:** Persist each step as it happens instead of at the end.
- **Why:** The run page shows no steps while a run is going; long free-tier runs look stuck.
- **Status:** no reply (noticed, not proposed before).
- **Code:** `apps/runs/services.py` (`pending_steps` buffer exists because Playwright callbacks run inside its event loop).
- **Effort:** medium.

### Shareable reports
- **What:** HTML/PDF page and JSON per run.
- **Status:** postponed (Phase 2).
- **Effort:** medium.

### Baselines, run-to-run diff and flake rate
- **What:** Store a passing run's focus path, flag changes later, repeat each run 3 times.
- **Status:** postponed (Phase 2).
- **Effort:** medium.

## UI and dashboard

### Planner form with model and key fields
- **What:** Fields appear for live providers with hints on server defaults; fixture option disabled where no scripted plan exists.
- **Status:** done (`1a20c1b`, `fdf7cf8`).
- **Code:** `templates/runs/list.html`.

### `openrouter/free` warning in the form
- **Status:** done (`fdf7cf8`).

### "Evaluate a real website" form
- **What:** Name, start page, goal, success checks (address contains / page shows text, at least one required), optional typed value, extra origins, max actions; remove button for added journeys.
- **Status:** done (`fdf7cf8`; moved into a dialog in `c79fb84`).
- **Code:** `apps/journeys/real_sites.py`, `apps/runs/views.py`, `templates/runs/list.html`.

### Redesign after your reference image
- **What:** Lavender backdrop, white app frame, tabs, start tiles, searchable journey list, recent runs, guide panel with stats, dark call-to-action card; run detail and overview in the same style; phone layout turns the runs table into cards.
- **Status:** done (`c79fb84`).
- **Code:** `templates/base.html`, `templates/runs/list.html`, `templates/runs/detail.html`, `templates/core/home.html`, `templates/runs/_illustration.html`.
- **Detail:** Loads Inter from Google Fonts; falls back to system fonts offline.

### Wider layout
- **What:** App frame up to 120rem with small margins.
- **Why:** You said the site was too narrow.
- **Status:** done (`6afc208`).

## Demo journeys and benchmark

### Simple demo: Wikipedia article search (AI only)
- **Status:** done (`c0bd434`). Passed live: run `08e3afde`, Groq `openai/gpt-oss-20b`, 8 steps. An earlier dashboard-added Wikipedia journey passed in 6 steps (`63831eb0`).
- **Code:** `fixtures/public/journey-manifest.json` (`demo-simple-wikipedia-search`).

### Complex demo: TodoMVC add and complete to-dos (AI only)
- **What:** Add "Buy milk" and "Call the clinic", complete "Buy milk"; success = both texts plus "1 item left".
- **Status:** done (`c0bd434`). Passed live: run `3fea7ef5`, Groq `openai/gpt-oss-120b`, 7 steps.
- **Detail:** Four earlier runs on `gpt-oss-20b` failed (missing Enter, re-typing, JSON 400s, then the 200,000 tokens-per-day cap).

### GOV.UK bank holidays journey
- **What:** Search GOV.UK and open "UK bank holidays".
- **Status:** dropped by me during selection: search results need many Tabs, slow on free tiers. You were not asked.

### W3C BAD before/after comparison
- **What:** Run the same journey on the inaccessible and accessible W3C demo sites to show barrier detection.
- **Status:** no reply (considered but not proposed to you; unconfirmed fit).

### Grow the benchmark to about 10 journeys
- **Status:** agreed, not started.

### Final course matrix (from project chat)
- **What:** 3 accessible + 5 broken clinic runs on one provider.
- **Status:** agreed, not started. Any one provider is acceptable (decided 29 Oct).

## Developer workflow (CLI, CI, tests, Docker)

### CLI and CI gate
- **What:** `accesspath run journey.yaml` with exit codes and a GitHub Action.
- **Status:** postponed to future scope (29 Oct: web only).
- **Effort:** medium.

### Run the test suite in the container
- **What:** `docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q` (112 passed, 9 skipped).
- **Why:** The host has no Playwright browsers; 11 browser tests fail on the host.
- **Status:** done (workaround documented).

### Port 8010 override
- **What:** Map web to 8010 because another local app holds port 8000.
- **Status:** partly done: documented in the handoff; the override file is not in the repo. Adding a `docker-compose.override.example.yml` is not started.
- **Effort:** small.

### `uv` cache workaround (from project chat)
- **What:** `UV_CACHE_DIR=.uv-cache`.
- **Why:** "Access is denied (os error 5)" on the user's machine.
- **Status:** done (documented).

### Git ownership workaround
- **What:** Per-command `safe.directory` environment variables.
- **Status:** done (documented). Fixing the folder owner is not started.

### Explicit `cryptography` dependency
- **Status:** done (`1a20c1b`).

### Folder cleanup (from project chat)
- **What:** Plans to `docs/planning`, old docs to `docs/archive`, Groq probes to `scripts/check_groq*.py`, Ruff E501 ignored for report builders.
- **Status:** done (in `d4c5299`).

### Put the repo on GitHub (from project chat)
- **Status:** done (`MICKEY0107/AccessPath-AI`).

### Make the repo private (from project chat)
- **Status:** rejected: the repo stays public (decided 29 Oct).

### Delete the already-pushed branch from GitHub
- **What:** Remove `origin/claude/project-thread-w787he`.
- **Status:** no reply (you later opened PR #1 from it, so likely not wanted; unconfirmed).

### Push local commits / update PR #1
- **Status:** postponed until you ask.

### Groq tidy-up or GitHub as first task (from project chat)
- **Status:** unconfirmed (GitHub done; Groq partly covered above).

### Run Claude Code locally to use plan limits (from project chat)
- **Status:** in progress on your side (moving to a local chat).

## Side ideas (VS Code assistant, voice extension)

### VS Code developer assistant
- **What:** Extension that flags keyboard problems while coding and runs a journey against localhost through the CLI, showing results in the Problems panel.
- **Status:** replaced (29 Oct) by a future MCP server, which works inside Claude Code, Cursor and Copilot agent mode.
- **Effort:** medium (about 3–4 weeks once the CLI exists; estimate).

### Chrome voice extension for motor-disabled users
- **What:** User speaks a goal; the agent operates the page in their own tab.
- **Status:** postponed (research only).
- **Why postponed:** It acts with the user's accounts, so it needs confirmation before submits or payments, privacy handling, user research, and comparison with OS voice control (Voice Access, Voice Control).
- **Effort:** large.

## Other

### Plan doc and handoff
- **Status:** done. Plan doc: https://claude.ai/artifact/HkebUHk6XuC9GTY29r9XQm; handoff: `PROJECT_HANDOFF.md`.

### Remove the stale dashboard-added Wikipedia journey
- **What:** "Wikipedia live search (real site)" duplicates the demo journey in the local DB.
- **Status:** no reply (noticed only).
- **Effort:** small (Remove button on the dashboard).

## Open questions I asked that you never answered

- Should the already-pushed branch be deleted from GitHub?
- When should the local commits be pushed (to update PR #1)?
- What is the final submission deadline?

## Broken or fragile, not fixed

- Groq JSON mode (non-gpt-oss models) still returns 400 "Failed to validate JSON" at times.
- Groq free caps: 8,000 tokens/minute and 200,000 tokens/day per model (seen on `gpt-oss-20b`); a capped model fails the run.
- Groq 429 messages include the organisation id, which is saved in local evidence.
- `openrouter/free` remains the `.env` default and is unreliable.
- Gemini untested since the fixes; last known result `GEMINI_TIMEOUT`.
- Steps are saved only when a run ends.
- Celery worker does not reload code; restart after engine changes.
- DNS rebinding between the host check and navigation is not prevented.
- `COMMIT_TYPED_VALUE_FIRST` can confuse two unnamed fields (edge case).
- Long Tab tours: if the target is more than 18 tab stops away, it is outside the observation window.
- TodoMVC's first link points to `http://todomvc.com` (different origin), which would cause a safety stop if followed.
- `ruff format --check` reports about 12 pre-existing files that would be reformatted.
- The older seeded pilots (original Wikipedia pilot, W3C smoke) still use scripted fallbacks; `run_public_pilot` depends on them.
- `apps/runs/tasks.py` sometimes shows line-ending-only changes.

## Recommended order for the next 5 items

1. **Confirm before blaming** — every later metric depends on not blaming the site for planner mistakes.
2. **Stop early on repeats** — saves free-tier tokens and ends looping runs with a clear reason.
3. **WCAG mapping plus unnamed-control and focus checks** — turns runs into findings developers and PMs can act on; TodoMVC gives a ready example.
4. **Retest Gemini and a pinned OpenRouter model on both demos** — gives a fallback provider when Groq caps hit and informs the mentor question.
5. **Final 3 accessible + 5 broken matrix and course write-up** — closes the open course items once the provider question is answered.
