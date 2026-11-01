# Adapting AccessPath

How to change AccessPath for another site, team, rule, model or code host. Every extension point below has tests next to it. Copy the nearest test and change it.

## The map

```
apps/            Django: pages, models, background tasks
  core/          overview, Status page, setup checks, check_setup
  journeys/      Journey model, rule settings form, real-site form
  runs/          runs, findings, report, Models page, rules page, code mapping, commands
  codebase/      repository bindings, demo repository, clone task
accesspath/      command line, CI reports (JSON, Markdown, SARIF), GitHub comment, MCP server, recorder
extension/       AccessPath Assist, the Chrome extension for keyboard and voice users
journeys/        example journey files for the command line and CI
engine/          no Django: the browser, planners, rules and code tools
  executor.py    the keyboard loop and request policy (incl. WebSockets)
  checks.py      focus, page and team-rule checks
  probes.py      Tab walk, activation probe, trap probe ("confirm before blaming")
  findings.py    collects findings and per-rule results
  rules.py       catalog loader, presets, team rules (CustomRuleV1)
  planner.py     planners (Gemini, OpenRouter, Groq, Ollama, scripted)
  repo_clone.py  safe clone · code_index.py index · secret_scan.py redaction
  code_locator.py where-to-fix and patches · locator_ai.py policy-bound AI search
  fix_verify.py  verify a patch on a copy of the demo site
  fixture_site.py fallback server for the demo site; serves a site folder for the CLI
  session_state.py saved sign-ins (filtered to a journey's sites)
rules/catalog.json   the reviewed rule catalog
fixtures/            the demo site (clinic + benchmark pages) and journey manifests
tests/               pytest; page_server.py serves throwaway pages to a real browser
```

The flow is described in `docs/ARCHITECTURE_AND_FLOW.md`.

## Settings (`.env`)

| Setting | Default | What it changes |
|---|---|---|
| `DJANGO_SECRET_KEY` | — (required) | Signs sessions and encrypts saved keys. Changing it makes saved keys unreadable. |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | `true`, `127.0.0.1,localhost` | Set debug off, and set the host names, before sharing the app |
| `POSTGRES_*`, `REDIS_URL`, `CELERY_RESULT_BACKEND` | local | Database and queue (Compose sets the service names for you) |
| `GROQ_*`, `GEMINI_*`, `OPENROUTER_*` (`_API_KEY`, `_MODEL`) | empty | Server-wide default keys and models; people can also save their own |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | empty | Local models (Docker: `http://host.docker.internal:11434`) |
| `CODE_SAFE_PROVIDERS` | empty | More providers allowed to read private code, for example a paid tier with a data agreement |
| `CODE_LOCATOR_USE_AI` | `true` | Turn the AI code search off completely |
| `PLANNER_MAX_CALLS_PER_RUN`, `PLANNER_*_RETRIES`, `PLANNER_MIN_CALL_INTERVAL_SECONDS` | 40, … | Cost and rate-limit behaviour |
| `EVALUATOR_MAX_STEPS`, `EVALUATOR_ACTION_TIMEOUT_MS`, `EVALUATOR_HEADLESS` | 56, 5000, true | The browser loop |
| `EVALUATOR_RUN_CHECKS` | `true` | Turn the per-step checks off, leaving only the journey outcome |
| `EVALUATOR_BROWSER_EXECUTABLE` | empty | Use an installed Chrome instead of Playwright's |
| `FIXTURE_ALLOWED_ORIGINS` | `http://127.0.0.1:8001` | Where the demo site lives (served automatically when nothing answers there) |
| `ALLOW_PRIVATE_NETWORKS` | `false` | Allow real-site journeys on private or local addresses (your own test servers only) |
| `AXE_CORE_VERSION`, `AXE_CORE_PATH` | 4.10.3, `vendor/…` | axe-core page rules |
| `REPO_STORAGE_ROOT`, `REPO_MAX_BYTES`, `REPO_MAX_FILES`, `REPO_CLONE_TIMEOUT_SECONDS` | `.runtime/repos`, 200 MB, 20 000, 120 | Repository copies and their limits |
| `DEMO_SITE_URL`, `DEMO_REPOSITORY_URL` | `http://127.0.0.1:8000`, project repo | Links printed by `demo_setup`, and the address shown for the demo repository |

## Common changes

### Evaluate another website

- **In the app:** **Evaluation runs → Add a real website** (read-only public sites).
- **As a reviewed, versioned journey** (with a scripted plan for repeatable demos): add an entry to `fixtures/public/journey-manifest.json` and run `seed_public_journeys`.
- **As a benchmark page with a known result:**
  1. Add the HTML page under `fixtures/clinic/benchmark/`.
  2. Add an entry with an `expected` block to `fixtures/benchmark/journey-manifest.json`.
  3. Run `seed_fixture_journeys`, then `run_benchmark --journeys <key>`.

### A rule for one product (no code)

Use **Rules → Your team's rules**. If none of the four checks fits, add one, as below.

### A new team-rule check

1. Add it to `CustomCheck` and `CUSTOM_CHECKS` in `engine/rules.py`: label, help text, suggested WCAG criterion and default fix.
2. Handle it in `CheckRunner._run_custom` in `engine/checks.py`. It receives the visible matches (up to 10) and the page's Tab walk.
3. Add a case to `tests/test_custom_rules.py`.

Keep checks declarative: a selector and numbers, never user-supplied code.

### A new catalog rule

1. Add the rule to `rules/catalog.json`:
   - id, title, WCAG criterion, ACT rules
   - check names, default severity
   - summary, fix hints, code patterns
2. Add it to the presets that should run it.
3. Bump `catalog_version` and `reviewed`.
4. Implement the check in `engine/checks.py`:
   - call `collector.checked(rule_id, applicable=...)` when it ran
   - call `collector.add(rule_id, ...)` for each problem, with `confirmed=False` for anything a scan can't prove
5. Add browser tests in `tests/test_keyboard_checks.py` using `serve_pages`.

### A new code pattern and patch

1. Detect the pattern in `engine/code_index.py` (`_index_markup` or `_index_styles`) with `_pattern(index, "<kind>", ...)`.
2. Add `<kind>` to the rule's `code_patterns` in the catalog, so the locator ranks lines carrying it first.
3. If the change is mechanical, add a branch in `suggest_fix` in `engine/code_locator.py` that returns `edits` (line number → new line). The patch and Verify come from those edits.

### A new AI provider

1. Write a client in `engine/` (see `groq.py` for an OpenAI-compatible API, or `ollama.py`) that returns a `ProposedActionV1` from the strict JSON schema.
2. Register a `kind` in `planner_from_config` (`engine/planner.py`) and a `PlannerProvider` choice (`apps/runs/models.py`, plus a migration).
3. Wire it up in the following places:
   - the client in `execute_configured_run` (`apps/runs/services.py`)
   - the option list `_planner_options` (`apps/runs/views.py`)
   - `RECOMMENDED_MODELS` and `list_models` (`apps/runs/model_settings.py`, `engine/provider_models.py`)
   - its code-safety entry in `engine/code_safety.py`, which decides whether it may read private code
4. Add it to the Status page checks in `apps/core/setup_checks.py`.

### Another git host

1. Add the host to `REPO_ALLOWED_HOSTS` in `config/settings/base.py`.
2. Add its token user name to `TOKEN_USERS` in `engine/repo_clone.py`.

Only `https://<host>/<owner>/<repo>` addresses are accepted.

## Testing

```powershell
./scripts/dev.ps1 test                       # everything, in the container
./scripts/dev.ps1 test tests/test_custom_rules.py -k reachable
uv run python -m pytest -q                   # natively (Python 3.13, uv sync, playwright install chromium)
uv run ruff check .
```

- Tests use SQLite in memory and run tasks in-process (`config/settings/test.py`). Browser tests start a real headless Chromium.
- `tests/page_server.py` has two helpers: `serve_pages({"/": html})` serves throwaway pages, and `executor_for(origin, tmp_path, rule_set=...)` builds an executor for them.
- Live-site tests are skipped unless `RUN_APPROVED_LIVE_TESTS=true`.
- CI (`.github/workflows/ci.yml`) runs ruff and the full suite on every push and pull request.

## Ground rules worth keeping

- **Confirm before blaming.** Only a deterministic check may mark a finding confirmed. AI output is never evidence on its own.
- **Never run repository code.** Never send code to a provider that `code_safety` doesn't allow.
- **Keys** are typed, saved encrypted, or kept in `.env`. They are never logged, stored in evidence or shown back, beyond a masked hint.
- **Every new page** must pass its own checks: keyboard only, visible focus, labelled controls, and no horizontal scroll at 390 px.
