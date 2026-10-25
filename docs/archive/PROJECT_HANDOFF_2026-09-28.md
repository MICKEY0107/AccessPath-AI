# AccessPath AI project handoff

**Last verified:** 28 September 2026  
**Current Phase 1 status:** `IN_REVIEW`  
**Evidence-weighted course progress:** 33.5%  
**Running local services:** PostgreSQL, Redis, fixture Nginx, Django web, and single-concurrency Celery worker

This is the concise continuation document for teammates and future work sessions. It records verified implementation, not planned capability.

## What is working

### Product workflow

- A Django dashboard lists two controlled appointment-booking journeys: one keyboard-accessible reference and one deliberately broken keyboard-barrier control.
- Each journey uses a native required dropdown to select `Live Gemini`, `Live OpenRouter`, or `Deterministic fixture contingency`.
- The chosen provider and model are persisted with the run. The application never silently changes a run from Gemini to OpenRouter or vice versa.
- Run-detail pages show outcome, terminal reason, planner metadata, step evidence, before/after screenshots, hashes, and issue highlighting.

### Evaluation engine and safety boundary

- Playwright performs keyboard-only execution against the approved fixture origin.
- A bounded planner proposes one typed action from a bounded observation.
- Deterministic policy validates origin, action, focus/target, and typing conditions before execution.
- Completion is determined by the declared completion policy, not the model. The deliberately broken fixture produces `blocked`, not `completed`.
- Provider failures, malformed output, unsafe output, quota, timeout, and retry exhaustion have visible metadata and bounded contingency behaviour.

### Provider implementation and reliability

- Gemini uses the Google GenAI SDK with structured JSON output.
- OpenRouter uses its chat-completions API with strict JSON Schema, `require_parameters`, response diagnostics with credential redaction, and a 768-token response budget.
- Both live providers use a process-wide pacing gate. The gate fixes a previous issue where creating a new client for a following run reset the minimum interval.
- Docker runs one Celery task at a time. The pacing fix therefore protects consecutive live runs in the current local deployment.
- Current observation: Gemini quota can fail even with a 15-second interval. OpenRouter `openrouter/free` has shown an Nvidia temporary-overload response and a length-limited response. Neither observed issue was HTTP 429, so fast reuse of the key is not established as the root cause.

### Documentation and presentation material

- `docs/ARCHITECTURE_AND_FLOW.md` contains the user flow, backend architecture, run lifecycle, and provider guardrails.
- `docs/PRESENTATION_OUTLINE.md` contains a seven-slide presentation sequence.
- `docs/DEMONSTRATION_RUNBOOK.md` contains an eight-minute demonstration script, persisted proof IDs, and a provider-outage contingency.
- `docs/TEAM_PROJECT_BRIEF.md` explains the problem, solution, users, completed work, current issues, and next steps in team-friendly language.

## Verified evidence and checks

| Item | Verified result |
|---|---|
| Accessible live proof | Gemini run `af03b14a-6700-4b91-a437-b8e3ada1de83`: `completed`, 29 calls, no fallback |
| Broken live proof | Gemini run `cf0e9180-6cd1-4d08-a7f1-972eba776d56`: `blocked`, 13 calls, `KEYBOARD_TARGET_NOT_REACHABLE`, no fallback |
| Latest focused/full quality check | 48 tests passed, Ruff passed, Pyright passed, Django check passed, migration-drift check passed |
| Dashboard browser check | The live `/runs/` page showed one accessible `Planner provider` combobox per journey with all three providers and no radio controls |
| Current local runtime | All five Compose services were running on 28 September 2026 |

## Remaining Phase 1 work

1. Confirm the evidence rule with the mentor/team: Gemini-only, or one fixed preflight-verified live provider. The current UI supports either, but evidence must be provider-pure.
2. Select a fixed model and run semantic preflight before starting the matrix. Do not use `openrouter/free` for the final evidence because it can route to changing upstream models.
3. Run the strict final matrix: 3 accessible completions and 5 broken runs with zero false completions and no deterministic fallback counted as live evidence.
4. Record the final run IDs, provider/model, outcomes, fallback status, and known limitation in `ACCESSPATH_AI_PROGRESS_LOG.md`.
5. Conduct and record a second-person manual keyboard/product review.
6. Insert team names, obtain the official presentation duration and rubric, rehearse the demo to that duration, and build the final slide deck from the outline.
7. Commit the demonstrated project revision, run the final Docker down/up rehearsal and full verification suite, then create the Phase 1 release tag after the exit review.

## Recommended next command sequence

```powershell
docker compose up -d
docker compose ps
docker compose exec -T web python manage.py check
docker compose exec -T web uv run --group dev python -m pytest -q
docker compose exec -T web uv run --group dev ruff check .
docker compose exec -T web uv run --group dev pyright
docker compose exec -T web python manage.py makemigrations --check --dry-run
```

Before final evidence, run the provider-specific semantic preflight. Use the configured interval and a fixed model. If the preflight reports quota, upstream overload, or malformed/length-limited output, record the failure and use the persisted proof in the presentation instead of claiming a new successful live run.

## Technology used so far

| Technology | Use in this project |
|---|---|
| Python 3.13, Django 5.2 | Web application, models, views, validation, run persistence, and dashboard |
| PostgreSQL 18.6 | Journeys, run state, step evidence, planner metadata, and artifact records |
| Redis 8.2 and Celery 5.6 | Background run queue and single-concurrency worker execution |
| Playwright | Browser automation limited to keyboard actions, observation capture, and screenshots |
| Pydantic | Versioned bounded observation, action, policy, completion, and evidence contracts |
| Google GenAI SDK | Gemini structured action proposals |
| OpenRouter HTTP API | Alternate structured action proposals with strict JSON Schema |
| Docker Compose | Reproducible local five-service environment and shared run-output volume |
| pytest, Ruff, Pyright | Tests, linting, and static type checks |
| Mermaid | Editable architecture and flow diagrams in Markdown |

## Scope that remains outside the current slice

- Authentication, multiple users, projects, authorization, cloud artifact storage, deployment, CI/CD, observability, and incident operations.
- Broader keyboard detector coverage and accessibility profiles for screen readers, visual checks, hearing, cognitive needs, mobile, documents, and native apps.
- Public-site transactions, payment, uploads, messaging, report export, benchmarks, compliance mapping, and production security hardening.

## Handoff rules

- Never expose API keys or paste `.env` values into documentation, commits, or chat.
- Never label deterministic fallback as Gemini or OpenRouter evidence.
- Never mix providers inside the final evidence matrix.
- Do not raise the 33.5% completion figure until the final matrix, exit review, demonstrated-revision commit, and release tag are complete.
