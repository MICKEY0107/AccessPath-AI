# AccessPath AI — Project Handoff

**Updated:** 2 November 2026 IST (release 1.0.0: stages 1–8 plus every future-scope item — CLI, GitHub Action, MCP server, signed-in journeys, record and replay, staging writes, baselines, live progress, Chrome extension; live runs and the course matrix still need the owner's machine and keys; pitch deck paused)
**Read this first in a new chat.** It is the single source of truth for where the project stands. Times in this file are IST unless marked UTC; the app's database stores UTC (IST = UTC + 5:30).

## 1. What the project is

AccessPath AI checks whether a person using only a keyboard can finish a real task on a website. A live LLM planner proposes one keyboard action at a time (Tab, Shift+Tab, Enter, Space, arrows, Escape, or Type a permitted value). A deterministic policy approves each action before Playwright presses the key. Every step is saved with focus evidence and before/after screenshots, and the run ends in an evidence-backed outcome: completed, blocked, inconclusive, agent error, safety stopped, or environment blocked.

**Product today:** a signed-in web app that runs a journey by keyboard, checks focus, names, skip links and focus order at every step, confirms any barrier with deterministic probes before blaming the site, maps findings to WCAG rules from a reviewed catalog, shows an accessibility report (with HTML/JSON export), and — when the site's repository is linked — points to the exact file and line with a reviewable patch.

It is a 5-credit college project (three-member team per the progress log). First users are **developers and product managers**. Goal statement (from the plan doc): run a declared task on a live site keyboard-only and return a verdict a developer or PM can act on — completed, or blocked at a named step with the WCAG criterion, a screenshot and a reproduction path.

Plan doc (goal, phases, gates, risks, sources): https://claude.ai/artifact/HkebUHk6XuC9GTY29r9XQm

Full list of every idea, suggestion and warning with status, effort and code locations: [`IMPROVEMENTS_BACKLOG.md`](IMPROVEMENTS_BACKLOG.md).

## 2. Decisions the owner has made (do not re-ask)

| Decision | Why |
|---|---|
| Free model tiers only: Gemini, OpenRouter, Groq, plus local Ollama (added 29 Oct) | College project; no paid API access. Ollama keeps private code on the machine |
| Web interface only; CLI and MCP server are future scope (29 Oct) | One interface to build well; it serves product managers directly |
| API keys may be remembered, encrypted and opt-in (29 Oct) | Replaces "never stored" for users who tick "Remember on this computer"; one-run keys keep the 1 h sealed path |
| The repo `MICKEY0107/AccessPath-AI` stays public (29 Oct) | Owner's answer |
| Course evidence may use any one provider (29 Oct) | Gemini was only the first choice; no Gemini-only requirement |
| Product shape: find, confirm, map to WCAG, point to the code (29 Oct) | Screens follow CodeImpact's layout (active codebase panel, model settings, report with tabs); see section 11 |
| AI only: demo journeys use a live planner, no deterministic or scripted steps | The point of the demo is AI planning on live or public-repo sites |
| Demo journeys: one simple, one complex, easy to understand | Owner had no specific sites in mind; asked for one of each |
| First users: developers and product managers | Owner's answer on 25 Oct |
| Local only: commit on the local branch; no pushes and no PRs until asked | Owner said "don't create a PR, change everything locally first" (after the picker branch had already been pushed). Owner then opened PR #1 themselves |
| Never touch `C:\code\RepoPilot` (CodeImpact) | Separate project. A session was opened there by mistake and stopped before it changed anything |
| Priority is the keyboard tool working like an industrial tool on actual sites | Owner's stated first priority; side ideas come later |
| The owner is moving to a separate local chat | To use their plan limits instead of Projects credit |

## 3. Open questions waiting for the owner

- **Deadline:** the final submission date (all stages are built; it now only decides how much live evidence to gather).
- **CodeImpact reference:** the owner wants its repo-clone and code-mapping code used as a reference. `C:\code\RepoPilot` is not connected to the AccessPath chat (an access request was blocked); the owner can add the folder in the desktop app or attach its files. Read only; never modify it.
- **Benchmark:** 12 fixture journeys exist with known results; which live public sites to add, if any (owner has none in mind).
- **When to push** the local commits and update PR #1. The demo's Code page binding of `MICKEY0107/AccessPath-AI` only sees the benchmark pages once they are pushed (the clinic pages are already on GitHub).
- **Release tag:** local tag `v1.0.0` exists (not pushed).

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
| `7a43242` Handoff expanded | 05:19 | Decisions with reasons, open questions, ideas register, live run results, known issues, exact next step; progress log 1.12 dated 26 October (IST) |
| `7d61d07` Improvements backlog | 05:21 | `IMPROVEMENTS_BACKLOG.md`: every idea, suggestion and warning from the project thread with status, effort and code locations; linked from section 1 |
| `975fa2d` Web plan recorded | 29 Oct | Handoff, backlog and plan doc record the web-only plan and the 29 October decisions |
| `dc91e99` Stage 1 | 29 Oct | Rules catalog (`rules/catalog.json`), presets, Rules page, `Journey.rule_config` |
| `87e8476` Stage 2 | 29 Oct | Confirm before blaming (`engine/probes.py`), findings (`engine/findings.py`, `Finding` table), `Run.failure_kind/diagnosis/rule_results` |
| `25db171` Stage 3 | 29 Oct | Focus and page checks (`engine/checks.py`), optional axe-core (`install_axe_core`) |
| `d3ae6a0` Stage 4 | 29 Oct | Accessibility report page and exports (`apps/runs/report.py`), 12-journey benchmark and `run_benchmark` |
| `eb1a4cd` Stage 5 | 29 Oct | Sign-in, Models page (encrypted remembered keys, List models, code-safety badge), Ollama provider, Code page (secure clone, index, secret scan) |
| `ef40c57` Stage 6 | 29 Oct | Where to fix (`engine/code_locator.py`), policy-bound AI search (`engine/locator_ai.py`), fix verification (`engine/fix_verify.py`) |
| Stage 7 | 29 Oct | Security review fixes (`tests/test_security_review.py`), README, runbook, presentation outline, architecture, backlog and this handoff |
| Stage 8 | 29 Oct | Product pass: team rules (`CustomRuleV1`, Rules page), `demo_setup` and the bundled demo repository (`RepoBinding.source`, migration codebase 0002), demo-site fallback server (`engine/fixture_site.py`), Status page and `check_setup`, overview checklist, WebSocket policy, `scripts/dev.ps1`/`dev.sh`, CI workflow, `docs/QUICKSTART.md`, `docs/USER_GUIDE.md`, `docs/ADAPTING.md`; ruff clean |
| `3c7526a` Run fixes | 2 Nov | Fixes found while running everything end to end in the build workspace (benchmark ignores team rules, labels) |
| Stage 10 (1.0.0) | 2 Nov | Everything from the future-scope list: `accesspath` CLI (journey files, JSON/Markdown/SARIF, exit codes, baselines, `login`, `record`), GitHub Action and example workflow, MCP server, signed-in journeys (encrypted saved sessions), record and replay, staging writes, baselines in reports, live run progress, prompt-cache usage, repeated-action stop, AccessPath Assist Chrome extension, `docs/CLI_AND_CI.md`, version 1.0.0 |

Development note: these stages were built in a cloud workspace with copies of the project's `.venv` packages, tested there (Playwright Chromium, SQLite test settings), and copied back here before each commit. `ruff` was not available there; run it locally.

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
| Rules catalog, presets, Rules page | Done (stage 1) | WCAG 2.2 + ACT IDs; disable needs a reason; ignores expire |
| Confirm a barrier before reporting it | Done (stage 2) | Tab walk, key probe with click comparison, trap probe; agent vs site vs provider failure |
| Map findings to WCAG with severity | Done (stages 2–3) | Every rule gets passed / failed / needs review / not applicable / not checked / disabled |
| Focus visible, focus obscured, skip link, focus order, unnamed controls, on-focus | Done (stage 3) | Static scans are "needs review" only |
| axe-core per page | Done (stage 3), optional | `python manage.py install_axe_core`; not installed means axe rules "not checked" |
| Accessibility report page, HTML/JSON export | Done (stage 4) | CodeImpact structure, rule-based plain-words panel |
| Benchmark of about 10 journeys | Done (stage 4) | 12 journeys; `run_benchmark`; 36/36 offline runs match |
| Sign-in | Done (stage 5) | `LoginRequiredMiddleware`; journeys and runs shared, repos and keys per person |
| Remembered encrypted keys, Ollama, code-safety badge | Done (stage 5) | |
| Active codebase (secure clone + index) | Done (stage 5) | Needs the rebuilt Docker image (git) |
| Where to fix, patches, AI search, fix verification | Done (stage 6) | Verification only for the bundled fixture pages |
| Team rules from a fixed set of checks | Done (stage 8) | Four checks: reachable with Tab, has a name, reached within N Tab presses, must not appear |
| One-command offline demo, Status page, getting-started checklist | Done (stage 8) | `./scripts/dev.ps1 setup`; `demo_setup`; `/status/`; `check_setup` |
| Cut planner cost further: prompt caching | Done (1.0.0) | Fixed instruction prefix; cached tokens shown on the reasoning tab |
| Stop early when the model repeats actions | Done (1.0.0) | `REPEATED_ACTION_NO_PROGRESS` after 3 identical keys on the same control with no change |
| Staging writes, saved-session logins, baselines | Done (1.0.0) | Journey settings page; sessions encrypted, owner-only, cut to the journey's sites; POST only to write origins within a budget, never during probes |
| CLI, MCP server, CI with SARIF and PR comments, record-and-replay | Done (1.0.0) | `python -m accesspath`, `.github/actions/accesspath`, `python -m accesspath mcp`; see `docs/CLI_AND_CI.md` |
| Chrome voice extension for motor-disabled users | Done (1.0.0), assistive only | `extension/` (AccessPath Assist): focus ring, skip link, landmarks, keyboard fixes, names, voice commands, page check. It changes the page in the user's own browser only and sends nothing to AccessPath; user research still recommended |
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
- **Live progress (fixed in 1.0.0):** steps are saved as they happen. Inside Playwright's greenlet Django hands out a different database connection, so `services.persist_steps` re-points the default alias to the run's own connection.
- **Security review (29 Oct, fixed in the stage 7 commit):** an independent review of the code side found 8 issues. All are fixed with tests in `tests/test_security_review.py`. Fixed: another person's journey could be re-linked; verification served fixture files from the clone; code locations were visible to everyone; multi-line private keys slipped past redaction; index snippets were not redacted; bad ports caused a 500; size was only checked after checkout; and page line numbers were not clamped. Hardening added: no git redirects, and the whole process group is killed on time-out. WebSockets are now under the same origin policy (stage 8): a socket to another origin is never connected, and the step's policy events record it.
- **Stage 8 review (29 Oct, fixed in the stage 8 commit):** a second independent review found 13 issues. All are fixed, with tests in `tests/test_custom_rules.py` and `tests/test_product.py`:
  - team-rule Tab checks now compare elements by a marker set during the Tab walk, not by CSS path (focus classes broke the paths)
  - a failing team rule no longer skips axe-core
  - disabled team rules and severity overrides are respected
  - every match is checked, not only the first ten
  - the fallback server refuses encoded hidden paths and is shared by overlapping runs
  - removing a team rule drops its ignores
  - the Status page fails fast when Redis is down
  - the image uses `uv sync --locked`, and setup renews the virtual-environment volume
  - "Load the demo" never rewrites existing journeys for non-staff and never takes journeys linked to another repository, and each person can have only one demo copy
  - `dev.ps1` passes `-v` and other flags through and tolerates stderr on Windows PowerShell 5.1
  - `tasks.verify_fix` falls back to the default rules
- **1.0.0 review (2 Nov, fixed in the 1.0.0 commit):** a third independent review of the CLI, CI action, MCP server, extension, sessions and staging found 18 issues; 17 are fixed with tests (`tests/test_cli.py`, `test_mcp.py`, `test_extension.py`, `test_sessions_replay_staging.py`):
  - a staging POST could be redirected (307) to another site; writes are now fetched with redirects off and checked
  - each journey gets its own SARIF category; SARIF paths are from the git root
  - `record` saved passwords; it now skips password and card fields and records each field's final value
  - another user could turn on staging writes for someone's signed-in journey; signed-in runs were visible to everyone
  - POSTs skipped the path check; background POSTs could stop a run
  - setup errors exited 1 instead of 4; bad run ids gave a 500
  - the extension changed deliberate `tabindex="-1"` patterns, could not undo its fixes, missed single-page-app content, and voice restarted in a tight loop
  - MCP: tool failures were protocol errors, private URLs were allowed, batches and client responses were mishandled
  - the PR comment could update a quoted copy, and several action calls shared one comment
  - Not changed (documented): `sync_orm_allowed` sets `DJANGO_ALLOW_ASYNC_UNSAFE` process-wide while steps are saved; keep Celery on its default prefork pool.
- **Demo journeys linked to someone else:** a journey links to one repository. When a second person loads the demo, their demo copy is not linked, and those reports show code only to the first person.
- **Checks change focus briefly:** focus checks blur and re-focus the control once, and page checks run a Tab walk, then restore focus exactly (verified by the scripted clinic plan). On real sites a blur handler (for example form validation) could react; the walk reloads the page if Tab itself navigates.
- **axe-core is not vendored:** neither PyPI nor npm was reachable from the build workspace. Run `install_axe_core` once (it downloads the pinned version from jsDelivr into `vendor/`, which git ignores).
- **Changing `DJANGO_SECRET_KEY` makes saved keys unreadable**; people must save them again.
- **Code mapping** is strongest for static HTML and React/Vue development builds (source hints). Minified production bundles fall back to text and class search.
- **Worker does not reload code:** restart it after engine changes.
- **Environment:** port 8000 is taken by another local app (`orchestrator_api` uvicorn from a Codex runtime); `uv` needs `UV_CACHE_DIR=.uv-cache`; the host has no Playwright browsers (11 browser tests fail on the host, pass in the container); Python file I/O defaults to cp1252 on this machine. Docker was down at the start of 25 Oct and is now running.

## 8. What I was in the middle of, and the exact next step

Nothing is half-done in code: stages 1–8 and release 1.0.0 are committed and the suite passes in the build workspace (see section 9 for the count). Everything below needs the owner's machine, Docker and API keys:

1. `./scripts/dev.ps1 setup` (rebuilds the image with git and the test tools, migrates, installs axe-core, runs `demo_setup`, prints the status check). Note the demo password it prints. `createsuperuser` is still needed for the admin.
2. `./scripts/dev.ps1 test` and `./scripts/dev.ps1 lint` in the container.
3. Live Gate 1 numbers: `docker compose exec worker python manage.py run_benchmark --provider groq --model openai/gpt-oss-120b --repeat 3`.
4. Course matrix: `run_fixture_matrix --provider groq --accessible-count 3 --broken-count 5`.
5. Try the 1.0.0 additions: `python -m accesspath run journeys/clinic-broken.json --repo .` (see `docs/CLI_AND_CI.md`), Journey settings, and the extension (`extension/README.md`).
6. Rehearse `docs/DEMONSTRATION_RUNBOOK.md`; push when ready so the Code page can bind the benchmark pages and the GitHub Action runs.

## 9. Run it locally

```powershell
docker compose -f docker-compose.yml -f <override> up -d      # see the port note
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser        # every page needs sign-in
docker compose exec web python manage.py seed_fixture_journeys  # clinic + 10 benchmark journeys
docker compose exec web python manage.py seed_public_journeys
docker compose exec web python manage.py install_axe_core       # optional
```

- **Rebuild once** (`--build`): the image now installs `git`, and compose adds a `repo_storage` volume for clones.
- **Local Ollama:** `OLLAMA_BASE_URL=http://host.docker.internal:11434` and `OLLAMA_MODEL` in `.env`.

- **Port:** map web to 8010 with an override file containing
  `services: { web: { ports: !override ["127.0.0.1:8010:8000"] } }`, then open http://127.0.0.1:8010/runs/.
- Restart the worker after engine changes: `docker compose restart worker`.
- `.env` holds `GEMINI_*`, `OPENROUTER_*`, `GROQ_*` keys and models (currently `models/gemini-3.5-flash-lite`, `openrouter/free`, `openai/gpt-oss-20b`). Never print or commit it.
- **Tests (in the container):** `docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test web python -m pytest -q` → **276 passed, 9 skipped** in the build workspace (`./scripts/dev.ps1 test`) (live-site tests are opt-in).
- Host lint: `UV_CACHE_DIR=.uv-cache uv run ruff check .`

## 10. Where the code is

- `engine/` — `executor.py` (keyboard loop, observation, completion signals including `url_contains` and `text_present`), `planner.py` (providers, retries, fallback or stop), `gemini.py` (system prompt), `groq.py` (strict schema), `openrouter.py`, `provider_http.py` (error text, Retry-After), `policy.py` (`COMMIT_TYPED_VALUE_FIRST`), `target_policy.py` (request rules, private-host block), `contracts.py`.
- `apps/runs/` — views, `services.py` (`execute_configured_run`), `tasks.py`, `credentials.py`.
- `apps/journeys/real_sites.py` — add-website form and public-host check.
- `fixtures/public/journey-manifest.json` — demo journeys (`demo-simple-wikipedia-search`, `demo-complex-todomvc`) and the older reviewed pilots.
- `templates/` — `base.html` (theme), `runs/list.html`, `runs/detail.html` (report), `runs/rules.html`, `runs/model_settings.html`, `runs/report_export.html`, `codebase/code.html`, `registration/login.html`.
- New in October: `rules/catalog.json`, `engine/rules.py`, `engine/probes.py`, `engine/findings.py`, `engine/checks.py`, `engine/dom.py`, `engine/ollama.py`, `engine/provider_models.py`, `engine/code_safety.py`, `engine/repo_clone.py`, `engine/code_index.py`, `engine/secret_scan.py`, `engine/code_locator.py`, `engine/locator_ai.py`, `engine/fix_verify.py`; `apps/codebase/` (repo bindings); `apps/runs/report.py`, `benchmark.py`, `code_mapping.py`, `model_settings.py`, `rule_views.py`; `fixtures/benchmark/journey-manifest.json` and `fixtures/clinic/benchmark/`. Architecture: `docs/ARCHITECTURE_AND_FLOW.md` (October section).

## 11. Web implementation plan (agreed 29 October 2026) — stages 1–6 done, stage 7 docs done

Full plan with the team split: the plan doc, section "Web implementation plan". The earlier three-phase plan is marked superseded there.

1. **Rules catalog and rules settings (week 1):** `rules/catalog.json` (2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.7, 2.4.11, 3.2.1, 4.1.2; 2.4.13 advisory) with WCAG/ACT sources, loader `engine/rules.py`, presets Essential / WCAG 2.2 AA / Strict, a Rules page (toggles, disable with reason, expiring ignores).
2. **Confirmed findings (weeks 1-2):** `Finding` type in `engine/contracts.py` and a table in `apps/runs`; confirm before blaming in `engine/executor.py` (section 8); site barrier vs agent failure.
3. **Keyboard checks and axe-core (weeks 2-3):** focus visible, focus obscured, skip link, focus order, unnamed controls; axe-core per page state; richer element details (`id`, classes, HTML snippet, DOM path).
4. **Accessibility report and Gate 1 (weeks 3-4):** `templates/runs/detail.html` in CodeImpact's structure (verdict badge, stat tiles, tabs Findings map / Fixes & re-checks / AI reasoning / Evidence, "In plain words" panel labelled rule-based or AI), recent reports, HTML/JSON export; benchmark of about 10 journeys; measure Gate 1.
5. **Active codebase and model settings (weeks 4-5):** Django sign-in first (no view requires login today; the app is safe only because it binds to 127.0.0.1). Repo URL, branch, one-time token, live site URL, Clone & analyze, recent repo chips, Remove clone; `RepoBinding` model; secure read-only shallow clone (no submodules or LFS, never run, symlink and size checks, `.env` and similar blocked, secret scan) and a front-end index. Model settings: recommended models, List, Save & use, Forget key, opt-in encrypted remembered keys, Ollama, a code-safety badge per provider (Gemini free tier and `openrouter/free` may not read private code).
6. **Where to fix (weeks 5-6):** findings map columns Exact match (rule-based index lookup), Likely cause (AI search agent: search/read/answer, each step approved by a policy) and Also affected; per-file fixes with a copyable patch (never applied to the user's repo) and Re-run; verify on the clinic fixture. The report must still work with no AI.
7. **Course deliverables (week 7):** final 3 accessible + 5 broken clinic runs on any one provider, write-up, presentation and demo script, release tag.

Team split: Engine (1 catalog, 2, 3) · Web UI (1 Rules page, 4, model settings in 5) · Code side (sign-in, clone and index in 5, then 6).

Gate 1 targets: 80% of live runs end in a trustworthy outcome; 90% of reported barriers confirmed real.

**Future scope (all done in 1.0.0, 2 Nov):** CLI, MCP server for coding assistants, CI with SARIF and PR comments, record-and-replay, the Chrome extension for keyboard and voice users, signed-in journeys, staging writes, baselines.
