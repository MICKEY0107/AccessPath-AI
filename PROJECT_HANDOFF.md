# AccessPath AI — Project Handoff

**Prepared:** 25 October 2026 (Asia/Kolkata)  
**Repository state:** `main` has no commits. Every tracked project file appears as untracked to Git, so there is no reliable Git history or commit-based diff.  
**Current runtime check:** Docker Desktop's Linux engine is not running. `docker compose ps` failed with `failed to connect to the docker API ... dockerDesktopLinuxEngine ... The system cannot find the file specified.`  
**Validation limitation:** `uv run pytest -q`, `uv run ruff check .`, and `uv run pyright` could not start because `uv` could not persist its interpreter-cache file: `Access is denied. (os error 5)`. This is an environment limitation, not a confirmed test failure.

## 1. Project overview

AccessPath AI is a local, evidence-driven web accessibility evaluator. It is for developers, reviewers, and a three-member course-project team who need to determine whether a person using only a keyboard can finish a defined web journey.

The core problem is that page-level accessibility scanners can identify some issues but cannot demonstrate whether a multi-step task remains usable as pages and focus states change. AccessPath AI runs a declared journey in a real browser, asks a bounded planner for one keyboard action at a time, applies fixed safety and outcome rules, and stores reviewable evidence.

The current goal is to complete and document the Phase 1 vertical slice: run an accessible appointment-booking fixture and a deliberately broken twin, preserve evidence for both outcomes, and collect a provider-pure live-model matrix of three accessible completions and five correctly blocked runs. The product does not claim full WCAG conformance.

## 2. Tech stack

| Area | Technology and locked/current version | Purpose |
|---|---|---|
| Language/runtime | Python `>=3.13,<3.14` | Application, worker, evaluator, and tooling |
| Web framework | Django `5.2.17` | Dashboard, persistence, views, templates, admin, and static/media routing |
| Database | PostgreSQL `18.6-bookworm` container; Psycopg `3.3.6` | Journeys, runs, evidence steps, and artifact metadata |
| Queue/worker | Redis `8.2-alpine`; Celery `5.6.3` | Background evaluation queue and single-concurrency worker |
| Browser automation | Playwright `1.63.0` | Keyboard-only browser actions, page observation, and screenshots |
| Validation contracts | Pydantic `2.13.5` | Strict observation, action, policy, and evidence schemas |
| Gemini integration | Google GenAI SDK `1.75.0` | Structured one-action proposals from Gemini |
| Alternate LLM integrations | OpenRouter and Groq HTTPS chat-completions APIs | Optional structured one-action proposals; clients use Python standard-library HTTP |
| Dependency/tool manager | `uv` with `uv.lock` | Reproducible Python dependencies |
| Testing and checks | pytest `8.4.2`, pytest-django `4.14.0`, Ruff `0.16.9`, Pyright `1.1.414` | Unit/integration tests, linting, and basic static checking |
| Local infrastructure | Docker Compose, Nginx `1.28-alpine` | Reproducible five-service local stack and static fixture hosting |
| Hosting/deployment | Local Docker Compose only | No cloud, production, CI/CD, domain, TLS, or managed hosting configuration is present; production deployment is unknown. |

## 3. Repository structure

```text
.
├── apps/                         Django apps
│   ├── core/                     Home page routes and view
│   ├── journeys/                 Journey model, migrations, and fixture/public seed commands
│   └── runs/                     Run/evidence models, views, service, Celery task, and commands
├── config/                       Django, ASGI/WSGI, and Celery configuration
│   └── settings/                 Base, local, and test settings
├── engine/                       Framework-independent evaluator, planner, provider, policy, and artifact logic
├── fixtures/
│   ├── clinic/                   Accessible and deliberately broken appointment-booking fixtures
│   └── public/                   Read-only public-journey manifest
├── infrastructure/               Nginx configuration for the fixture service
├── templates/                    Django templates for the home page and evaluation-run UI
├── tests/                        Automated tests for policy, providers, fixtures, executor, views, and commands
├── docs/                         Architecture, demos, research, status, presentation, and prior handoff material
│   ├── planning/                 Master project plan and implementation plan
│   └── archive/                  Superseded 28 Sep handoff and original synopsis report
├── scripts/                      DOCX synopsis report generators and manual Groq API checks
├── output/                       Git-ignored local browser evidence for native runs
├── .env.example                  Environment-variable template; contains no usable credentials
├── docker-compose.yml            Local PostgreSQL, Redis, Nginx fixture, Django, and Celery services
├── Dockerfile                    Development image definition
├── manage.py                     Django management entry point
├── pyproject.toml                Python project/developer-tool configuration
├── uv.lock                       Locked Python dependency graph
├── README.md                     Primary setup and operational instructions
├── ACCESSPATH_AI_PROGRESS_LOG.md Project progress, decisions, evidence, and change log
└── PROJECT_HANDOFF.md            This continuation document
```

Notable documents:

- `docs/ARCHITECTURE_AND_FLOW.md`: Mermaid diagrams for user flow, backend architecture, and run lifecycle.
- `docs/PROJECT_COMPONENT_STATUS.md`: previously verified component inventory and Phase 1 status.
- `docs/DEMONSTRATION_RUNBOOK.md`: demonstration sequence and known proof IDs.
- `docs/RUNBOOK_REAL_SITE_PILOT.md`: opt-in, read-only public-site pilot boundary.
- `docs/AccessPath_AI_Synopsis_Report_Refined.docx`: refined synopsis report with the project architecture diagram.
- `docs/archive/PROJECT_HANDOFF_2026-09-28.md`: earlier, shorter handoff dated 28 September 2026; this root file is the current comprehensive handoff.
- `docs/planning/ACCESSPATH_AI_MASTER_PROJECT_PLAN.md` and `docs/planning/ACCESSPATH_AI_IMPLEMENTATION_PLAN.md`: long-form scope, safety, delivery, and phase plans.

## 4. Architecture

### Main components and data flow

1. An evaluator opens the Django home page or `/runs/`, chooses an active `Journey` and a planner provider, and submits `POST /runs/journeys/<journey_id>/start/`.
2. Django validates the provider configuration, creates a `Run`, persists the selected provider/model, and queues `accesspath.execute_run` in Redis/Celery.
3. The single-concurrency Celery worker loads the journey and uses `apps.runs.services.execute_configured_run` to construct the selected planner and `KeyboardExecutor`.
4. Playwright opens the declared URL. The executor builds a bounded observation: current URL, focused element, up to 40 interactive elements, bounded visible text, a short action history, permitted synthetic input, and remaining step budget.
5. Gemini, OpenRouter, Groq, or the deterministic fixture planner proposes exactly one typed keyboard action. A process-wide pacing gate applies each provider's minimum call interval.
6. Deterministic policy validates the action, focus/target rules, typing permission, URL/origin/path restrictions, budgets, and browser safety. Only approved keyboard actions reach Playwright.
7. The executor captures before/after observations and screenshots. `RunStep` and `RunArtifact` records are persisted, with local files stored below `MEDIA_ROOT` (`output/` in native development; shared `run_output` volume in Compose).
8. Fixed completion and barrier rules decide `completed`, `blocked`, `inconclusive`, or an explicit issue outcome. Django renders the run-detail evidence page at `GET /runs/<uuid>/`.

### HTTP routes and command interfaces

| Interface | Purpose |
|---|---|
| `GET /` | Project home page |
| `GET /runs/` | Active journeys, recent runs, and provider/status/outcome filters |
| `POST /runs/journeys/<int:journey_id>/start/` | Persist and queue a new evaluation run |
| `GET /runs/<uuid:run_id>/` | Run outcome, planner metadata, step evidence, screenshot links, and hashes |
| `/admin/` | Django admin |
| `seed_fixture_journeys` | Seed the two versioned clinic journeys from fixture manifests |
| `seed_public_journeys` | Seed approved read-only public journeys |
| `preflight_gemini` / `preflight_openrouter` | Check a configured model's structured-action behaviour before evidence collection |
| `run_fixture_matrix` | Run a strict provider-specific accessible/broken test matrix |
| `run_public_pilot` | Run the reviewed, opt-in public read-only pilot |

### Database schema

| Model | Key fields and relationships |
|---|---|
| `Journey` | `name` (unique), `goal`, `start_url`, `execution_mode`, `allowed_origins`, `completion_policy`, `evaluation_config`, active flag, timestamps. One journey has many runs. |
| `Run` | UUID primary key; `journey` FK; status; outcome; Celery task ID; planner provider/model/metadata; terminal reason; error detail; timestamps. Indexed by journey and descending creation time. |
| `RunStep` | FK to `Run`; unique step number per run; JSON evidence; timestamp. Append-only evidence record. |
| `RunArtifact` | FK to `Run` and optional FK to `RunStep`; kind, local relative path, SHA-256, timestamp. |

`Run` statuses are `queued`, `starting`, `running`, `finalizing`, `succeeded`, `failed`, and `cancelled`. Outcomes are `pending`, `completed`, `blocked`, `inconclusive`, `environment_blocked`, `safety_stopped`, `agent_error`, and `system_error`.

### External integrations and safety boundary

- **Google Gemini:** Google GenAI SDK with JSON-schema responses. Requires `GEMINI_API_KEY` and `GEMINI_MODEL`.
- **OpenRouter:** `https://openrouter.ai/api/v1/chat/completions`, strict JSON Schema, a recorded resolved model when supplied, and redacted diagnostic messages. Requires `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.
- **Groq:** `https://api.groq.com/openai/v1/chat/completions`, JSON-object response format. Requires `GROQ_API_KEY` and `GROQ_MODEL`.
- **Controlled fixture:** Nginx serves static accessible and broken clinic sites only at `127.0.0.1:8001` in the local Compose configuration.
- **Public pilot:** only opt-in, read-only approved journeys; `RUN_APPROVED_LIVE_TESTS` defaults to `false`.

No provider controls browser execution, completion, or safety decisions. Deterministic fixture fallback is never to be presented as live-model evidence, and provider evidence sets must not be mixed.

## 5. Setup and run

### Prerequisites

- Python 3.13
- `uv`
- Docker Desktop configured for Linux containers
- For native browser tests, a Playwright browser; on Windows, optionally Chrome at `EVALUATOR_BROWSER_EXECUTABLE`

### Environment variables

Copy `.env.example` to `.env`; never commit `.env`. These names are used by the project:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_HOST
POSTGRES_PORT
REDIS_URL
CELERY_RESULT_BACKEND
GEMINI_API_KEY
GEMINI_MODEL
OPENROUTER_API_KEY
OPENROUTER_MODEL
GROQ_API_KEY
GROQ_MODEL
PLANNER_MAX_CALLS_PER_RUN
PLANNER_CALL_TIMEOUT_SECONDS
PLANNER_MIN_CALL_INTERVAL_SECONDS
PLANNER_MAX_429_RETRIES
PLANNER_429_BACKOFF_SECONDS
PLANNER_MAX_TRANSIENT_RETRIES
PLANNER_TRANSIENT_BACKOFF_SECONDS
FIXTURE_ALLOWED_ORIGINS
ALLOW_PRIVATE_NETWORKS
EVALUATOR_MAX_STEPS
EVALUATOR_ACTION_TIMEOUT_MS
EVALUATOR_HEADLESS
EVALUATOR_BROWSER_EXECUTABLE
RUN_APPROVED_LIVE_TESTS
```

### Local Compose workflow

```powershell
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fixture_journeys
docker compose exec web python manage.py seed_public_journeys
docker compose ps
```

Open `http://127.0.0.1:8000/runs/`. The fixture service is expected at `http://127.0.0.1:8001`.

### Quality and schema checks

```powershell
uv run pytest -q
uv run ruff check .
uv run pyright
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Equivalent commands inside the Compose web container are documented in `README.md`. Do not claim they passed until they run successfully in the current environment.

### Provider preflight and matrix commands

```powershell
docker compose exec web python manage.py preflight_gemini --list-only
docker compose exec web python manage.py preflight_gemini --model <verified-model> --calls 3 --interval 15
docker compose exec web python manage.py preflight_openrouter --model <verified-model> --calls 3 --interval 20
docker compose exec web python manage.py run_fixture_matrix --provider <gemini-or-openrouter-or-groq> --accessible-count 3 --broken-count 5
```

Use a specific, preflight-verified model for final evidence. `openrouter/free` is documented as suitable only for a smoke check because it can select different upstream models.

### Deployment

There is no verified deployment command beyond local Docker Compose. Production hosting, deployment, release automation, backups, TLS, and CI/CD are unknown/not implemented.

## 6. Current status

### Works according to the latest project records (last documented verification: 28 September 2026)

- Django dashboard, journey selection, provider selector, run persistence, worker queue, keyboard-only Playwright executor, evidence records, screenshot gallery, and fixture journeys.
- Accessible and deliberately broken appointment-booking fixtures, including the declared `clinic_barrier.v1` unreachable time-slot control.
- Explicit Gemini, OpenRouter, Groq, and deterministic fixture planner selection; provider/model persistence; no silent cross-provider change.
- Fixed action policy, origin/path safety checks, action/step/call/time limits, completion rules, and human-readable outcome descriptions.
- Gemini evidence recorded in project documentation: accessible run `af03b14a-6700-4b91-a437-b8e3ada1de83` completed in 29 calls without fallback; broken run `cf0e9180-6cd1-4d08-a7f1-972eba776d56` was blocked in 13 calls without fallback, with `KEYBOARD_TARGET_NOT_REACHABLE`.
- The previous handoff records 48 passing pytest tests plus Ruff, Pyright, Django check, and migration-drift check on 28 September 2026. This has not been re-run successfully on 25 October 2026 due the `uv` permission failure noted above.

### Partly done

- Phase 1 remains in review. The required uninterrupted, provider-pure post-fix matrix (three accessible completions plus five broken runs) is still pending.
- Gemini, OpenRouter, and Groq code paths exist, but a fixed live provider/model must be preflighted and selected before final evidence collection.
- The read-only public-site pilot is designed and seeded but is opt-in and not the primary demonstration.
- Documentation and synopsis reports exist, including a refined report with an architecture diagram. The report is not a substitute for the final evidence matrix.

### Broken, unavailable, or unverified now

- **Docker runtime unavailable today:** `docker compose ps` failed with `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`
- **Local `uv` validation blocked today:** `uv run pytest -q`, `uv run ruff check .`, and `uv run pyright` failed before executing due `Failed to query Python interpreter` and `failed to persist temporary file ... Access is denied. (os error 5)` in the sandbox cache directory.
- **Provider reliability remains unresolved:** Gemini quota can fail despite a 15-second pacing interval. OpenRouter `openrouter/free` previously returned an Nvidia temporary-overload response and a length-limited completion. These observations are documented in `ACCESSPATH_AI_PROGRESS_LOG.md`; they do not prove that the keys are faulty.
- **No commit history:** Git reports `fatal: your current branch 'main' does not have any commits yet`; current files are untracked. There is no commit, tag, branch history, or release revision to rely on.
- **Production deployment:** unknown/not implemented.

## 7. Recent work and decisions

The latest recorded work is dated 28 September 2026. It includes:

- Added explicit Gemini/OpenRouter/deterministic provider selection, later extended with Groq. Provider and model are stored before queueing so evidence cannot be mislabelled.
- Replaced provider radio controls with a required native dropdown after UI review.
- Added OpenRouter strict JSON-schema support, semantic preflight, provider-specific matrix support, metadata labels, and credential-redacted diagnostics. The reason was to provide an auditable alternate live provider without hiding provider changes.
- Added a process-wide provider pacing gate. The reason was that constructing a fresh client in a following run had previously reset the minimum call interval. The local worker remains single-concurrency.
- Improved fixtures and run-list UX: clear accessible-versus-broken fixture messages, friendly blocked-result wording, explicit issue-evidence labels, and in-page run filters that preserve page position.
- Added architecture/run-flow diagrams, a presentation outline, a demonstration runbook, and a prior project handoff.
- Created and refined the synopsis report. In the most recent report edit, the `Current Development Status`, `Current Evidence`, `Limitations and Risk Management`, and `Work Plan` sections were removed; remaining sections were renumbered, forward-work wording was removed from the conclusion, and the architectural diagram was retained. The resulting DOCX was visually checked and passed the document accessibility audit at that time.
- The project deliberately separates historical Gemini proofs from the pending final post-fix matrix. This prevents individual successful runs from being overstated as a complete Phase 1 gate.

## 8. Next steps

### Priority TODOs

1. Restore a usable local environment: start Docker Desktop Linux containers and resolve the `uv` cache permission issue; re-run the quality suite and record dated results.
2. Confirm the academic evidence rule: Gemini-only or any one named preflight-verified live provider. Do not infer this choice.
3. Select one fixed model from the approved provider, run provider-specific semantic preflight, and record the provider/model and outcome.
4. Run the strict provider-pure matrix: three accessible and five broken journeys; require zero false completions and do not count deterministic fallback as live-model evidence.
5. Record final run IDs, provider/model, outcomes, terminal reasons, fallback status, and limitations in `ACCESSPATH_AI_PROGRESS_LOG.md`.
6. Obtain a second-person manual keyboard/product review and record it.
7. Initialize/repair Git history only with the repository owner's approval, then commit the demonstrated revision and create a Phase 1 release tag after the exit review.
8. Insert official team names, presentation duration, rubric requirements, and any mentor decision into project documentation; these are currently unknown.

### Open questions

- Does the assessment require Gemini specifically, or is a verified provider-neutral live model acceptable?
- What are the official review date, presentation duration, rubric, and permitted backup-demo format?
- Which fixed provider/model currently has reliable quota and structured output for the final matrix?
- Who owns the repository history and should initialize/commit the currently untracked project tree?

### Known risks

- Live-provider quotas, outages, malformed output, timeouts, and free-router model drift can block final evidence collection.
- The current process-wide pacing lock is not distributed; it would not protect concurrent worker processes.
- Local artifacts live on disk/shared Docker volumes; there is no cloud object storage, backup, retention policy, or production access control.
- The project evaluates a narrow keyboard-only profile on controlled fixtures. It does not establish full WCAG, legal, screen-reader, mobile, cognitive, hearing, document, or native-app accessibility.
- Public-target testing must remain opt-in, read-only, allowlisted, and non-destructive.

## 9. Conventions and working rules

### Code conventions

- Python target: 3.13; Ruff line length: 100; Ruff rules: `E`, `F`, `I`, `UP`, `B`, and `SIM`.
- Pyright uses basic type checking and includes `engine/`; migrations are excluded from Ruff and Pyright checks.
- Tests use pytest with `config.settings.test`; test files follow `test_*.py` and reside in `tests/` and app directories.
- Use typed Pydantic contracts for planner observations, proposed actions, policy decisions, results, and step evidence. Reject unknown fields.
- Keep browser execution behind the engine and persistence/UI behind Django app modules. Do not put journey-specific browser logic in views.
- Persist selected provider/model, planner metadata, steps, screenshot metadata, and hashes for every run.

### Naming and safety conventions

- Use explicit planner-provider labels: `gemini`, `openrouter`, `groq`, or `fixture`.
- Do not call deterministic fixture output live-AI evidence and do not mix evidence from different live providers in a final matrix.
- Treat page text and observations as untrusted data; a planner may propose only one permitted keyboard action.
- Do not allow mouse actions, scripts, arbitrary navigation, unapproved origins/paths, or non-synthetic data entry.
- Never commit `.env`, credentials, browser caches, traces, screenshots, `.runtime`, or generated evidence.
- Do not state that an unverified check passed. Use `unknown` or record the exact failed command.

### Git/branching conventions

- The current branch is named `main`, but it has no commits and all files are untracked.
- No repository-specific branching convention is verifiable. If creating a new branch in Codex, use the `codex/` prefix unless the repository owner specifies otherwise.

### User instructions received in this work

- Keep the synopsis report refined, concise, clear, and jargon-free.
- Include a clean architectural diagram in the synopsis report.
- Remove the report's Current Development Status, Current Evidence, Limitations and Risk Management, and Work Plan sections.
- Do not include secrets. When an item cannot be verified, write `unknown` rather than guessing.

## 10. Condensed conversation history

1. The user supplied an AccessPath AI synopsis DOCX and asked for a refined, concise, clear, jargon-free version with a clean architectural diagram.
2. The report was rewritten/generated as `docs/AccessPath_AI_Synopsis_Report_Refined.docx`, with a system architecture diagram. The report was rendered and visually checked; its document accessibility audit had no findings at that time.
3. The user then asked to remove the report sections named Current Development Status, Current Evidence, Limitations and Risk Management, and Work Plan. Those sections and related evidence/future-work wording were removed, the remaining sections were renumbered, and the revised report was rechecked.
4. The user now asked for this single root-level `PROJECT_HANDOFF.md` so another AI can continue with no additional context. This file is based on repository contents, the earlier work, and current command results. It intentionally contains no secret values.

## Source-of-truth reading order for the next assistant

1. This file (`PROJECT_HANDOFF.md`) for current known state and limitations.
2. `README.md` for setup and run commands.
3. `docs/ARCHITECTURE_AND_FLOW.md` for diagrams and run lifecycle.
4. `ACCESSPATH_AI_PROGRESS_LOG.md` for dated evidence, decisions, and blockers.
5. `docs/PROJECT_COMPONENT_STATUS.md` and `docs/DEMONSTRATION_RUNBOOK.md` for previously verified capabilities and presentation flow.
6. `apps/runs/services.py`, `engine/executor.py`, `engine/policy.py`, and `engine/contracts.py` before changing evaluation behavior.
