# AccessPath AI — Implementation and Delivery Plan

**Document role:** Execution plan for the keyboard-first course project  
**Version:** 1.3  
**Date:** 27 September 2026  
**Status:** Phase 1 technical vertical slice complete; presentation metadata and release tag pending  
**Phase 1 review boundary:** First week of October 2026; development is governed by phase exit criteria rather than time-based task allocation  
**Related source of truth:** `ACCESSPATH_AI_MASTER_PROJECT_PLAN.md`  
**Progress record:** `ACCESSPATH_AI_PROGRESS_LOG.md`

---

## 1. Purpose

This document converts the master project plan into executable development phases, work packages, review gates, and acceptance criteria. It is the team's delivery plan; the master plan remains authoritative for product scope, architecture, safety, terminology, and long-term direction.

The immediate objective is not to create a superficial percentage by counting pages or files. It is to demonstrate a credible vertical slice of the core idea:

> From the AccessPath AI interface, start a declared task; let a bounded AI planner choose permitted keyboard actions; execute those actions in a real browser; capture deterministic evidence; and report whether the journey completed, was blocked, or was inconclusive.

The project review must show working software. Documentation, login/signup screens, mock dashboards, and unconnected UI do not count as core implementation progress.

---

## 2. Confirmed constraints and decisions

These items came directly from the team and are not assumptions:

- Development begins from zero; no implementation currently exists.
- The Phase 1 review is in the first week of October 2026; Phases 1A–1F define the required development progression before that boundary.
- The review must contain a working local demonstration.
- Public deployment is not required for the Phase 1 review.
- The product should have a clear homepage and a usable path for creating and viewing evaluation runs.
- The first meaningful task will be a multi-step appointment/booking-style form, not login or signup.
- Autonomous model-guided navigation is part of the Phase 1 target.
- Every browser interaction made by the evaluator must use the permitted keyboard-action policy.
- The guaranteed demonstration may use a team-owned accessible/broken fixture.
- Supporting public-site evaluation is desirable, but there is no authorized private or production target.
- Public targets may therefore be used only for non-destructive, read-only, rate-limited tasks that their published purpose and policy permit.
- PostgreSQL, Redis, and the application will run locally.
- The available model access is a free Gemini API key.
- No paid hosting, managed Redis, or paid object storage is currently available.
- The master plan specifies a three-member course team. One teammate is strongest in AI/ML; most integration work will occur on the lead developer's local machine.

### Information still to record, without blocking Phase 1A

- Exact review date and presentation duration.
- Team member names against the three roles.
- Whether the W3C BAD supporting run will be shown live or as previously captured evidence; the target itself is now selected.
- Whether the evaluator permits a prerecorded backup if internet/model access fails.

These items are tracked in the progress log and must not be silently guessed.

---

## 3. Strict scope interpretation

### 3.1 What “30–40% progress” will mean

For reporting purposes, the percentage applies to the **keyboard-first course delivery**, not the lifetime product vision that later includes screen-reader, visual, hearing, cognitive, mobile, document, and native profiles.

The Phase 1 target is a completed planning foundation plus one end-to-end technical vertical slice. If its acceptance criteria are met, the team may defensibly report approximately **35% of the keyboard-first course delivery**. The team must also show the evidence behind that percentage.

| Course-delivery phase | Weight | Cumulative when complete |
|---|---:|---:|
| Phase 0 — Scope, architecture, delivery plan, and risk controls | 5% | 5% |
| Phase 1 — Working technical vertical slice | 30% | 35% |
| Phase 2 — Durable platform, authorization, security, and storage | 15% | 50% |
| Phase 3 — Keyboard detector catalogue and broader journeys | 20% | 70% |
| Phase 4 — Safe authenticated/transactional journeys and reporting | 10% | 80% |
| Phase 5 — Evaluation, compliance traceability, and research results | 10% | 90% |
| Phase 6 — Deployment hardening, final documentation, and defense | 10% | 100% |

Weights are planning weights, not automatically earned by elapsed time. A phase contributes only when its exit evidence is recorded in the progress log.

### 3.2 Phase 1 must-have scope

The Phase 1 vertical slice must include:

1. A semantic Django homepage explaining the project and current keyboard-only profile.
2. A run-creation screen with a fixed approved target and task preset.
3. An accessible multi-step appointment fixture.
4. A deliberately broken twin containing a known keyboard barrier.
5. A Playwright browser evaluator using real keyboard events only.
6. An observer that records URL, title, focused element, available action candidates, and state changes.
7. A Gemini planner that returns one typed action at a time.
8. A policy validator that rejects mouse actions, arbitrary scripts, unapproved URLs, excessive input, and unsupported keys.
9. A deterministic completion check and explicit `completed`, `blocked`, `inconclusive`, or `system_failed` result.
10. Step evidence visible in the product: action, focused element, result/state change, and at least selected screenshots.
11. A local PostgreSQL-backed run record.
12. A local Redis/Celery worker so browser work does not run in the Django request.
13. A repeatable command sequence and demo script.

### 3.3 Phase 1 should-have scope

- Polling-based progress page while a run executes.
- A simple axe-core baseline kept separate from journey findings.
- One safe, read-only run against an approved public demonstration target.
- Cancellation and action/time budgets.
- A deterministic planner adapter for repeatable tests and offline demonstration recovery.
- Basic CI or a local quality command covering lint, type checks, and tests.

### 3.4 Explicitly deferred until later phases

- User registration, OIDC, team invitations, and full multi-tenant authorization.
- Real booking submission on a third-party site.
- Real payments, emails, messages, uploads, or account changes.
- Transactional outbox, worker heartbeat/lease recovery, dead-letter administration, and production retry hardening.
- MinIO/S3 integration; the current implementation may use a project-local artifact adapter behind the approved `ArtifactStore` interface.
- Server-Sent Events; short polling is adequate for the local vertical slice.
- Production deployment, TLS, domain setup, backups, and managed services.
- Complete keyboard detector catalogue.
- Claims of WCAG conformance or whole-site accessibility.
- Visual, audio, screen-reader, mobile, document, and native profiles.

Deferred means scheduled later, not removed from the project.

---

## 4. Demonstration definition

### 4.1 Guaranteed demonstration

The primary demo must run on a versioned, team-owned fixture because it is stable, legal to test, and capable of proving both success and failure paths.

The fixture is an original static **AccessPath Clinic** site in `fixtures/clinic/`, served by a dedicated Docker Compose `fixture` service using a pinned Nginx image. It is published only as `127.0.0.1:8001:80`; AccessPath AI uses `127.0.0.1:8000`. The fixture uses versioned HTML/CSS and minimal vanilla JavaScript only for controlled time-slot state and page navigation; it has no external API, database, email, or payment dependency. Fixture mode sets `FIXTURE_ALLOWED_ORIGINS=http://127.0.0.1:8001`; public-target mode sets `ALLOW_PRIVATE_NETWORKS=false` and never inherits that origin. This separate configuration is mandatory and tested before browser evaluation begins.

The fixture will contain two variants with the same appointment task and visual design:

- **Accessible variant:** every required control is reachable and operable by keyboard; focus order is logical; validation is recoverable; confirmation is observable.
- **Broken variant:** the fixed KBD-001 time-slot barrier defined below prevents completion. It must contain no second intentional barrier.

The journey goal should be concrete and machine-checkable, for example:

> Book the earliest available general consultation using the provided synthetic name and email, stop on the confirmation page, and do not perform any external side effect.

The fixture's confirmation is local test state only. It sends no message and creates no real appointment.

#### Fixed broken-fixture ground truth (`clinic_barrier.v1`) — resolves MS-005

- **Journey step:** Step 3, “Select an appointment time,” after a date has been chosen and before the review step.
- **Accessible implementation:** each available slot is a native `<button type="button">` in sequential focus order. `Enter` or `Space` selects it, exposes `aria-pressed="true"`, and enables the native Continue button.
- **Broken implementation:** the same enabled, visible slot buttons have `tabindex="-1"`. There is no focusable group entry point, arrow-key handler, keyboard shortcut, or alternative select control. Pointer activation still selects a slot, proving the functionality exists but is excluded from sequential keyboard use.
- **Blocking condition:** Continue remains disabled until a slot is selected, so a keyboard-only user cannot reach the review or confirmation step.
- **Expected rule:** `KBD-001 — Required task control unreachable by sequential keyboard navigation`.
- **Expected journey outcome:** `blocked` only after the detector has sufficient traversal evidence; never `completed`.
- **Required evidence:** inventory of the visible enabled slot buttons and their `tabindex=-1`; a complete bounded forward traversal and reverse traversal of the step with no slot receiving focus; unchanged selected-slot state; disabled Continue control; before/after state fingerprints; and a screenshot/focus trace.
- **Negative control:** the accessible twin must use the same labels, data, styling, and completion policy and must complete with keyboard input.
- **Fixture invariant:** the machine-readable manifest ID is `clinic_barrier.v1`, fixture version is recorded with every run, and any change to the barrier requires a new manifest version.

### 4.2 Supporting public-target demonstration

The public-target run is evidence of portability, not the guaranteed source of a detected flaw. It must:

- use a target intentionally published for accessibility demonstration/testing, or a benign public page whose terms permit ordinary automated access;
- remain read-only and avoid login, submission, booking, messaging, downloads, or account changes;
- use a fixed allowlist and low action/rate budget;
- stop on bot protection, CAPTCHA, consent ambiguity, or unexpected navigation;
- distinguish an environment block from an accessibility finding; and
- avoid claiming a defect unless a human reproduces it and the evidence supports the rule.

The research-backed target order is:

1. **Optional supporting proof:** [W3C WAI Before and After Demonstration](https://www.w3.org/WAI/demos/bad/), comparing approved “before” and “after” navigation/survey pages without submission.
2. **Preferred stretch proof:** [Deque University MarsCommuter](https://dequeuniversity.com/demo/mars/), limited to bounded focus-order inspection and stopped before search/booking submission.
3. **Later regression controls:** selected WAI-ARIA APG examples and a pinned local copy of selected GDS accessibility-tool-audit cases.

The full first-party research, limitations, and source citations are recorded in `docs/research/PUBLIC_TEST_TARGETS.md`. The W3C run is supporting evidence only: capture it when stable and permitted, but never make the controlled demonstration depend on it. Deque is removable under the scope-cut rules.

For both public targets, the browser context must allow only reviewed origins/path prefixes and safe retrieval methods (`GET` and `HEAD`, plus `OPTIONS` only if demonstrated necessary). It must abort `POST`, `PUT`, `PATCH`, `DELETE`, `CONNECT`, `TRACE`, unknown methods, and unapproved cross-origin navigation. Method filtering does not by itself prove safety, so action labels/destinations associated with submit, send, buy, reserve, confirm, delete, download, upload, and login remain blocked.

### 4.3 Demonstration sequence

1. Show the homepage: problem, keyboard-first scope, safety boundary, and system flow.
2. Open “New evaluation,” select the accessible appointment fixture, and show the task and allowed actions.
3. Start the run and show that the Django request returns while Celery performs browser work.
4. Show the progress page updating through polling.
5. Open the completed report and show the step sequence, keyboard actions, focus evidence, screenshots, and completion signal.
6. Run or open the broken twin and show the documented blocker without false completion.
7. If stable and approved, show the read-only public-target run.
8. End with the limitations and the next phase, not a compliance claim.

### 4.4 Demo success metrics

The Phase 1 slice is ready only when:

- the accessible fixture completes in three consecutive controlled runs;
- the broken fixture produces zero false completions in five controlled runs;
- every executed browser action is present in the allowed keyboard schema;
- a malformed or unsafe Gemini action is rejected by policy;
- the report links every terminal conclusion to recorded evidence;
- a fresh setup can be started using the documented commands;
- the demo can be completed within the presentation time once that time is known; and
- the team can explain which decisions are made by AI and which are deterministic.

If Gemini or internet access fails during the review, the team may switch to the deterministic adapter only if it is visibly labeled as a contingency. It must never be presented as a live model run.

---

## 5. Technical slice

```text
Django Templates + HTMX/polling
        |
        | create/view run
        v
Django application + PostgreSQL
        |
        | Celery task ID
        v
Local Redis broker ---> Celery browser worker
                              |
                              v
                    Evaluation Engine
            Observer -> Planner -> Policy -> Executor
                |          |                    |
                |          v                    v
                |       Gemini API       Playwright/Chromium
                |                               |
                +---------- evidence <----------+
                              |
                              v
                PostgreSQL + local artifact adapter
```

### Required module boundaries

- `apps/runs`: run creation, status, events, results, and UI/API views.
- `apps/journeys`: fixed task definitions, input fixtures, and completion signals.
- `engine/contracts`: Pydantic observation, action, evidence, and result models.
- `engine/observer`: browser state extraction only.
- `engine/planner`: `Planner` interface, Gemini adapter, deterministic test adapter.
- `engine/policy`: authorizes every proposed action independently of the model.
- `engine/executor`: translates approved actions into Playwright keyboard calls.
- `engine/detectors`: first reproducible keyboard blocker logic.
- `workers`: Celery task and persistence adapter.
- `fixtures`: accessible and broken appointment site variants.

### `StepEvidenceV1` contract — resolves MS-002

The engine emits one immutable record for every proposed action, including rejected actions. The platform persists and displays the same versioned contract; it must not create a second report-specific evidence shape.

```json
{
  "schema_version": "step_evidence.v1",
  "run_id": "uuid",
  "step_number": 1,
  "observed_at": "2026-09-26T10:00:00Z",
  "url_before": "http://127.0.0.1:8001/accessible/slots/",
  "url_after": "http://127.0.0.1:8001/accessible/slots/",
  "focus_before": {"fingerprint": "sha256:...", "role": "button", "name": "Continue", "test_id": "continue"},
  "focus_after": {"fingerprint": "sha256:...", "role": "button", "name": "Continue", "test_id": "continue"},
  "proposed_action": {"action": "enter", "value": null, "target_hint": "Continue", "purpose": "advance"},
  "policy_decision": {"outcome": "approved", "code": "ACTION_ALLOWED"},
  "executed_action": {"action": "enter", "value": null},
  "action_result": {"status": "no_effect", "meaningful_progress": false, "error_code": null},
  "state_fingerprint_before": "sha256:...",
  "state_fingerprint_after": "sha256:...",
  "duration_ms": 184,
  "artifact_refs": [{"artifact_id": "uuid", "kind": "screenshot_after", "sha256": "..."}],
  "rule_evaluation_refs": ["uuid"],
  "evidence_source": "keyboard_observation"
}
```

Required field rules:

- `run_id` is a UUID; `step_number` is a positive integer unique within the run; `observed_at` is UTC RFC 3339.
- `url_before` and `url_after` are normalized, policy-approved URLs with credentials and sensitive query values removed.
- `focus_before` and `focus_after` are nullable `ElementEvidenceV1` objects containing only `fingerprint`, `role`, sanitized accessible `name`, and optional `test_id`; each string is capped at 256 characters.
- `proposed_action` is always present. `policy_decision.outcome` is `approved` or `rejected` and `code` is a stable machine-readable enum.
- `executed_action` is present only after approval. A rejected proposal must have `executed_action: null` and `action_result.status: rejected`.
- `action_result.status` is one of `effect_observed`, `no_effect`, `rejected`, or `execution_error`; `meaningful_progress` is deterministic and never supplied by the model.
- Fingerprints use the algorithm recorded in the run configuration. `duration_ms` is a non-negative integer.
- `artifact_refs` contain opaque IDs, type, and digest—never local paths or signed URLs. `rule_evaluation_refs` contain persisted evaluation IDs.
- `evidence_source` is the literal `keyboard_observation` during the current profile; it must never be relabeled as assistive-technology evidence.

The record excludes raw credentials, full HTML, model chain-of-thought, unredacted form values, and inline binary content. Once appended, it is not updated; later rule evaluations and artifacts are linked by ID through new records or finalization metadata.

### `ArtifactStoreV1` contract — resolves AG-002

The engine depends only on this interface. The local adapter used before Phase 2 and the later MinIO/S3 adapter must implement the same behavior.

| Operation | Input | Success output | Failure contract |
|---|---|---|---|
| `put` | `ArtifactWriteV1` metadata plus a binary stream | `ArtifactRefV1` | Raise `ArtifactStoreError` with `size_limit_exceeded`, `digest_mismatch`, or `unavailable` |
| `get_authorized_url` | artifact UUID, authorized project subject, expiry seconds | short-lived URL or local authenticated download route | `not_found` or `forbidden`; never return a filesystem path |
| `delete` | artifact UUID and retention reason | deletion audit result | `not_found` is idempotent success; other failures are retried/recorded |

`ArtifactWriteV1` contains `run_id`, `kind` (`screenshot_before`, `screenshot_after`, `trace`, `axe_raw`), MIME type, byte count, SHA-256 digest, and retention class. `ArtifactRefV1` contains only UUID, run UUID, kind, MIME type, byte count, digest, and `storage_state="available"`. The adapter returns success only after the exact byte count and digest are verified. The local adapter writes beneath a gitignored `.runtime/artifacts/<run-id>/` directory; it permits screenshots up to 5 MiB and traces up to 30 MiB. A failed required artifact write marks the run `system_failed / ARTIFACT_WRITE_FAILED`; no report may be finalized as successful with missing required evidence.

The engine may call `put` but never creates URLs. Django authorizes read access before calling `get_authorized_url`. No adapter accepts raw credentials in artifact metadata, and no report stores a local path or signed URL.

### Planner runtime configuration (`planner_runtime.v1`) — resolves FG-001 and MS-004

The model tier's live quota is account- and model-specific. On 27 September 2026 the application discovered the account's generate-content models through the provider API, preflighted the selected exact identifier, and completed the required live repetition matrix. The verified Phase 1 configuration is:

```text
PLANNER_MAX_CALLS_PER_RUN=30
PLANNER_CALL_TIMEOUT_SECONDS=30
PLANNER_MIN_CALL_INTERVAL_SECONDS=15
PLANNER_MAX_CONCURRENT_CALLS=1
PLANNER_MAX_429_RETRIES=1
PLANNER_429_BACKOFF_SECONDS=30
PLANNER_MAX_TRANSIENT_RETRIES=2
PLANNER_TRANSIENT_BACKOFF_SECONDS=15
PLANNER_ACTION_HISTORY_WINDOW=8
EVALUATOR_MAX_STEPS=56
```

Before enabling Gemini in the UI, the team must run account-specific model discovery, complete a paced structured-output preflight on the actual development network, and record the exact model and evidence. Where the provider does not expose RPM/TPM/RPD values through the API, empirical preflight and matrix evidence must be recorded without inventing quota numbers. On timeout, final 429, malformed/unsafe output, exhausted transient retry, or unavailable provider, the resilient planner requests one executor-controlled restart at the allowlisted journey start and uses the deterministic fixture plan. The UI labels that outcome as a contingency with its reason; the strict Gemini evidence command rejects it rather than counting it as live-model evidence.

The planner must not receive database credentials, Gemini API keys, raw secrets, or authority to execute actions. It proposes. Policy authorizes. The executor performs only authorized keyboard operations.

---

## 6. Phase 1 development phases

The phases below must be completed in dependency order before the Phase 1 review boundary. They are defined by outcomes and exit evidence, not by hours or calendar-day allocation. A later phase may be explored in parallel only when it does not bypass the preceding phase's gate.

Use these role labels until names are recorded:

- **Lead/Integration:** Django, database, Celery, Playwright integration, final merge, and local demo environment.
- **AI/ML:** planner contract, Gemini structured output, prompt/policy tests, and model reliability measurements.
- **QA/Fixture/Documentation:** accessible/broken fixture, manual keyboard ground truth, test evidence, progress log, and presentation material.

All members review safety and demo claims.

#### Binding project ownership and continuity — resolves TP-001 and TP-002

For the current project, `LEAD_INTEGRATION` is the project initiator and local development-machine operator; `AI_ML` is the teammate responsible for Gemini/planner work; and `QA_FIXTURE` is the remaining teammate responsible for fixture ground truth and evidence. Every task, pull request, test failure, and feedback item must have exactly one of these role IDs as owner; “whole team” is not an owner. The role roster is binding from Phase 1A, and full names are added to the progress log before the first shared merge.

The repository must have a shared remote before functional code is merged. Phase 1A cannot close until one non-lead teammate performs a clean local setup from the repository using `uv sync`, Docker Compose, and a personal `.env` created from `.env.example`. `AI_ML` is the backup integration operator if `LEAD_INTEGRATION` is unavailable. The lead must create `docs/runbooks/local-stack.md` with start, stop, reset, migration, worker, test, and recovery commands; no API key, database dump, artifact, virtual environment, browser cache, or `.env` file may enter Git.

### Phase 1A — Project foundation and runnable platform

**Objective:** Establish one repeatable application foundation before building evaluator behavior.

Deliverables:

- Initialized Git repository and approved monorepo structure.
- Pinned Python environment with `pyproject.toml` and `uv.lock`.
- Django project with separated local and test settings.
- Local PostgreSQL and Redis services through Docker Compose.
- Celery application with a verified test task.
- Semantic Django homepage and primary navigation.
- Minimal `Journey` and `Run` models required by the vertical slice.
- Ruff, Pyright, pytest, pytest-django, and one reproducible quality command.
- Documented startup commands and environment variables with no committed secrets.
- Shared remote repository, `.gitignore`, `.env.example`, and a second-member clean-setup check.
- Course-requirements register populated from the official BML Munjal course rubric or mentor instructions; unknown requirements are explicitly marked `PENDING_INSTITUTION` rather than guessed.

Exit evidence:

- Django system checks pass.
- Migrations apply to a clean PostgreSQL database.
- The homepage loads and is manually keyboard navigable.
- A Redis/Celery test task completes.
- Lint and tests execute successfully.
- A non-lead teammate completes a clean setup from the shared repository.
- The course-requirements register identifies the rubric source, owner, due date, and evidence state for synopsis, review, report, presentation, and viva requirements; missing institutional information remains visibly `PENDING_INSTITUTION`.

**Gate 1A:** Do not begin UI polish or model integration until the application, database, and worker start reliably.

### Phase 1B — Controlled journey and ground truth

**Objective:** Create one owned journey with known accessible and broken outcomes.

Deliverables:

- Original AccessPath Clinic appointment fixture on a separate local origin.
- Accessible and deliberately broken variants with identical task data and completion criteria.
- Synthetic form data and a local-only simulated confirmation.
- Machine-readable expectation manifest for the deliberate barrier.
- Fixed allowlisted targets and task presets in the run-creation form.
- Manual keyboard ground-truth record and fixture route/state tests.

Exit evidence:

- A human completes the accessible fixture without mouse input.
- Two reviewers reproduce the intended broken behavior.
- The broken variant cannot accidentally complete through an alternative control.
- No real side effect, personal data, or external message is created.

**Gate 1B:** The controlled outcome must be independently verified before the evaluator is judged against it.

### Phase 1C — Deterministic keyboard evaluation kernel

**Objective:** Prove observation, policy, keyboard execution, evidence, and completion logic independently of AI.

Deliverables:

- Pinned Playwright Chromium environment.
- Pydantic contracts for `Observation`, `ProposedAction`, `ApprovedAction`, `StepEvidence`, and `RunResult`.
- Allowed action schema for `Tab`, `Shift+Tab`, `Enter`, `Space`, arrows, `Escape`, and text entry into the focused editable control.
- Browser observer for URL, title, active element, role/name/type, visible text summary, and focus/state fingerprint.
- Deterministic action policy with action, navigation, repetition, and execution budgets.
- Playwright executor that never uses mouse actions, direct DOM activation, or arbitrary target scripts.
- Deterministic planner adapter and deterministic completion oracle.
- Structured step events and selected screenshots through the local `ArtifactStore` adapter.
- Celery execution and Django run-status persistence.

Exit evidence:

- The deterministic adapter completes the accessible fixture.
- The broken fixture never receives a false `completed` outcome.
- Logs prove every interaction passed through policy and keyboard execution.
- Cancellation or budget exhaustion terminates Chromium and records an explicit terminal reason.

**Gate 1C:** AI integration cannot become the primary execution path until the observer, policy, executor, and completion oracle work without AI.

### Phase 1D — Bounded autonomous Gemini planner

**Objective:** Add goal-directed autonomous navigation without transferring execution authority to the model.

Deliverables:

- Provider-neutral `Planner` interface.
- `google-genai` adapter using the current stable model available to the configured account.
- Provider structured output with independent Pydantic validation.
- Bounded planner context containing only observation, goal, permitted input reference, and short action history.
- Page-content isolation: target text is treated as untrusted data, never policy instructions.
- Rejection of selectors/scripts, mouse actions, unsupported keys, unknown fields, unsafe text, and target-policy violations.
- Bounded handling of malformed model responses.
- Recorded Gemini quota preflight and `planner_runtime.v1` configuration.
- Metrics for action count, latency, token usage where available, and terminal result.
- Prompt-injection and policy-violation test fixtures.

Exit evidence:

- Gemini completes a controlled accessible run end to end.
- The recorded RPM/TPM/RPD limits support the configured action budget and repeated-run plan.
- Each model call either returns or times out within `PLANNER_CALL_TIMEOUT_SECONDS`; no worker remains blocked after timeout or terminal 429.
- Three consecutive controlled accessible runs complete before demo freeze.
- Invalid structured output becomes a bounded retry or explicit planner error.
- A policy-violating proposal is recorded and rejected before execution.
- The broken fixture has zero false completions across five controlled runs.

**Gate 1D:** A model-produced success statement can never override the deterministic completion oracle.

### Phase 1E — Product workflow, reporting, and portability proof

**Objective:** Turn the engine into an understandable product workflow and demonstrate bounded cross-site portability.

Deliverables:

- Completed homepage, new-run, progress, result, and evidence views.
- Polling-based progress without blocking the Django request on browser execution.
- Report showing profile, target, goal, state, outcome, terminal reason, actions, focus evidence, screenshots, budgets, and limitations.
- Accessible error/status announcements without unexpected focus movement.
- Optional axe-core baseline kept separate from journey findings.
- Reviewed W3C BAD target manifest and navigation-only before/after comparison.
- Deque MarsCommuter bounded focus-order inspection only after all required gates pass.
- End-to-end smoke test from run creation to evidence-backed report.
- Verified clean-start instructions.

Exit evidence:

- The complete controlled workflow operates through the product UI.
- Progress is understandable without manually refreshing the page.
- Reports separate journey findings, axe observations, model/platform failures, and uncertainty.
- Any optional public run causes no external state change and makes no unsupported claim.

**Gate 1E:** An unstable or disallowed public target is removed from the live sequence; safety is never weakened to preserve a demonstration.

### Phase 1F — Verification, review, and demonstrated release

**Objective:** Produce a repeatable, honest, tagged demonstration package.

Deliverables:

- Feature-frozen demonstrated candidate.
- Passing lint, type checks, migrations, unit/integration tests, and manual keyboard tests.
- Completed repetition matrix for accessible and broken fixtures.
- Closed P0/P1 findings and recorded P2/P3 backlog.
- Progress log containing commit IDs, commands, screenshots, metrics, feedback, and limitations.
- Concise presentation covering problem, scope, architecture, working flow, evidence, progress, limitations, and next phase.
- Rehearsed live demo plus a labeled static/recorded recovery artifact if course rules permit.
- Tagged demonstrated revision such as `phase1-v0.1.0`.

Exit evidence:

- A clean-start rehearsal succeeds.
- The complete demo sequence succeeds twice without code changes.
- Required tests are green on the tagged revision.
- Each member can explain their contribution and the AI/deterministic boundary.
- Known limitations and deferred work are visible.

**Gate 1F:** After tagging, only reviewed blocker fixes may enter the demonstrated release, followed by full regression of the demo path.

---

## 7. Scope-cut and recovery rules

When time is short, cut in this order:

1. Remove styling polish and animations.
2. Remove the public-target live demo; retain controlled fixtures.
3. Defer axe-core presentation while preserving journey evidence.
4. Reduce screenshot frequency while retaining structured step evidence.
5. Use polling instead of SSE.
6. Keep one appointment journey rather than adding another journey.

Do **not** cut:

- real keyboard-only Playwright execution;
- the accessible/broken controlled pair;
- policy validation between Gemini and execution;
- deterministic completion and explicit uncertainty;
- evidence for every terminal conclusion;
- safe target restrictions; or
- disclosure when a deterministic contingency adapter is used.

### Gate-driven recovery matrix — resolves FG-004

| If this gate is not met | Required response | What may continue | What must not be claimed |
|---|---|---|---|
| Gate 1A | Repair the local foundation; do not begin browser/AI work | Documentation and fixture markup preparation | A working evaluation platform or 35% vertical-slice progress |
| Gate 1B | Reduce the fixture's content, not its accessible/broken paired ground truth | Static appointment pages and manual review | Reproducible barrier detection |
| Gate 1C | Remove public-target, axe, styling, and extra-report work; repair the deterministic kernel | Deterministic fixture evidence only | Autonomous navigation or trustworthy findings |
| Gate 1D | Treat Gemini integration as failed; use only the visibly labeled deterministic contingency for a technical demonstration | All non-AI platform work | Live autonomous AI navigation |
| Gate 1E | Remove all public-target evidence and retain the controlled fixture report | Local controlled demonstration | Cross-site portability |
| Gate 1F | Freeze scope, close P0/P1 defects, and retest; if unresolved, demonstrate only the last passing tagged revision | Last passing revision and honest limitations | Features added after the last passing revision |

The controlled fixture is the sole non-negotiable Phase 1 proof. The project percentage is recalculated from the last passed gate; it is never retained merely because later work was attempted.

### Stop conditions

Stop and repair the foundation when:

- the evaluator uses mouse or arbitrary DOM activation;
- Gemini can bypass the action policy;
- the broken fixture is falsely marked completed;
- browser processes remain after cancellation/failure;
- a public run would submit data or cause an external effect;
- secrets or personal data appear in prompts, logs, screenshots, or Git; or
- the demo requires manual database editing to succeed.

---

## 8. Standards-based phase review process

Every phase closes through the same evidence-driven review. A calendar date alone does not close a phase.

### 8.1 Review inputs

- Demonstrable user outcome.
- Acceptance-criteria checklist.
- Automated test results and manual keyboard results.
- Security/privacy/safety review relevant to the phase.
- Accessibility review of AccessPath AI itself.
- Metrics and reproducibility evidence.
- Known defects, limitations, and deferred items.
- Feedback from teammates, mentor/evaluator when available, and test users where appropriate.

### 8.2 Feedback classification

| Priority | Meaning | Required handling |
|---|---|---|
| P0 | Safety, data-loss, secret exposure, unauthorized effect, or unusable demo | Stop; fix before further work or demonstration |
| P1 | Incorrect core outcome, policy bypass, false completion, or broken primary workflow | Fix before phase closes |
| P2 | Important quality, evidence, accessibility, or maintainability weakness | Schedule in the next phase and assign an owner |
| P3 | Improvement or future-scope suggestion | Record in backlog; do not destabilize the current phase |

### 8.3 Improvement loop

1. Capture feedback verbatim and identify its source.
2. Reproduce or clarify the issue.
3. Classify P0–P3 and identify the affected requirement.
4. Decide: accept, modify, defer, or reject with reason.
5. Implement the smallest coherent improvement.
6. Add or update a regression test where possible.
7. Re-run the affected acceptance criteria.
8. Record evidence and decision in the progress log.
9. Update the master plan only when product scope/architecture changes; create an ADR only for costly, surprising trade-offs.

### 8.4 Phase decision

Each review ends with one of:

- **GO:** all exit criteria met; next phase may begin.
- **CONDITIONAL GO:** only named P2 items remain with owners and deadlines.
- **NO-GO:** a P0/P1 issue or missing core evidence prevents phase closure.

---

## 9. Later development phases

### Phase 2 — Durable platform and security foundation

**Weight:** 15%  
**Objective:** Convert the Phase 1 prototype into a restart-safe and access-controlled platform.

Build:

- Final Django domain models and migrations.
- Atomic run + transactional outbox creation.
- Idempotent outbox dispatcher and Celery task execution.
- Retry, heartbeat/lease, cancellation, timeout, cleanup, and dead-letter behavior.
- MinIO locally and S3-compatible `ArtifactStore` adapter.
- Object-level project authorization and OIDC decision/implementation.
- Target verification, URL normalization, DNS/IP/redirect/egress controls.
- Artifact retention/redaction and signed authorized access.
- Structured logs, run correlation, and basic metrics.

Exit criteria:

- Accepted runs survive Django restart and recover from broker publication failure.
- Duplicate delivery cannot create a duplicate logical outcome or side effect.
- Cross-user/project access tests are denied.
- Private, loopback, link-local, metadata, and unsafe redirect targets are blocked.
- Worker cancellation removes browser children and scratch artifacts.
- Evidence persists outside worker-local storage.

### Phase 3 — Keyboard evaluation breadth

**Weight:** 20%  
**Objective:** Expand from one proof journey to a defensible keyboard evaluation engine.

Build:

- Versioned keyboard accessibility profile.
- Detector catalogue from the master plan, each with applicability and evidence rules.
- Accessible/broken positive and negative fixtures per detector.
- Focus order/history, keyboard reachability, activation, trap/escape, composite-widget, validation recovery, and focus-restoration checks.
- Rerun and immutable comparison.
- Per-state axe-core baseline kept separate from journey findings.
- Planner regression suite and deterministic replay.
- Action, token, time, origin, and loop budgets.

Exit criteria:

- Every supported detector has accessible and broken ground truth.
- Supported findings meet the pilot precision/recall targets or are honestly re-scoped.
- Repeated-run agreement is measured.
- False completion remains within the master-plan target.
- The same journey can run under deterministic and Gemini planners without changing evidence rules.

### Phase 4 — Safe complete journeys and reporting

**Weight:** 10%  
**Objective:** Prove the keyboard evaluator beyond a single local appointment fixture.

Build:

- At least one authenticated fixture journey.
- Representative booking, form submission, sandbox checkout, messaging/upload, recovery, or account-management fixture journeys selected by the team.
- Execution modes: fixture, observe-only, and sandbox-transactional.
- Secret references and worker-only resolution.
- Typed payment/mail/message/upload sandbox adapters.
- Expected-effect assertions, cleanup verification, and `cleanup_failed` outcome.
- Versioned report schema, export, and rerun comparison.

Exit criteria:

- No real payment, recipient, personal data, or uncontrolled production effect is used.
- Each transactional fixture verifies expected effect and cleanup.
- Secret values never enter planner context, ordinary logs, or report content.
- Reports distinguish automatic, semi-automatic, manual, planned, and not-applicable coverage.

### Phase 5 — Evaluation and compliance traceability

**Weight:** 10%  
**Objective:** Produce academically defensible results rather than only a product demo.

Build:

- Frozen benchmark and protocol.
- Two independent manual reviewers and adjudication procedure.
- Matched-state comparison with axe-core.
- Precision, recall, false completion, false block, inconclusive rate, reproducibility, latency, and model-cost analysis.
- Error taxonomy and negative-result analysis.
- Versioned WCAG 2.2 coverage register and applicable India/international reporting profiles.
- Explicit limitations and manual-review requirements.

Exit criteria:

- Raw confusion matrices and benchmark versions are retained.
- Evaluation can be reproduced from a tagged revision.
- Unsupported rules are not represented as passing.
- Compliance language follows the master-plan disclaimer.
- Results include failures and ambiguous cases, not only successful examples.

### Phase 6 — Deployment, hardening, and final defense

**Weight:** 10%  
**Objective:** Prepare a production-shaped release and complete course delivery.

Build:

- Containerized web and worker images with separate resource policies.
- Free/approved staging platform selection; paid services require a later explicit decision.
- Production settings, health checks, migrations, backups, retention, and recovery procedure.
- CI quality/security gates and release tagging.
- OpenTelemetry-compatible correlation and error tracking configuration.
- Threat-model review, security test closure, and privacy checklist.
- Final report, presentation, demo script, architecture diagrams, and evidence appendix.

Exit criteria:

- A fresh environment can deploy from documentation.
- Staging passes smoke, authorization, keyboard, worker-failure, and retention tests.
- No critical/high security issue remains open.
- Final claims match the implemented profile and measured results.
- Demo and backup evidence work from a tagged release.

---

## 10. Testing strategy by delivery layer

| Layer | Required tests |
|---|---|
| Contracts | Pydantic schema validation, unknown/unsafe actions, version compatibility |
| Domain | run/outcome transitions, completion oracle, budgets, retry classification |
| Django | forms/serializers, permissions, object scoping, migrations, API responses |
| Queue | publication failure, duplicate delivery, cancellation, worker crash, timeout |
| Engine | observation, policy, keyboard mapping, fingerprints, loop detection, cleanup |
| Planner | structured output, malformed response, prompt injection, budget exhaustion |
| Fixtures | accessible success, intended broken failure, negative controls |
| Storage | authorized artifact access, digest, retention, deletion, missing upload |
| Security | SSRF classes, unsafe redirects, hostile content, stored XSS, secret redaction |
| Product E2E | create run → progress → evidence-backed report; keyboard-only product use |
| Evaluation | repeated runs, ground-truth agreement, confusion matrix, matched-state baseline |

### Phase 1 minimum automated tests

- Allowed and rejected action-contract tests.
- Policy rejects mouse/script/unsupported key/target escape.
- Completion oracle accepts only the fixture confirmation state.
- Accessible fixture deterministic smoke test.
- Broken fixture does not false-complete.
- Django create-run and status/report tests.
- Celery task failure maps to `system_failed`, not `blocked`.

---

## 11. Engineering workflow

### Source control

- Protect the demonstrated main branch through reviewed changes.
- Use short-lived branches and small pull requests where team workflow permits.
- Never commit `.env`, API keys, database dumps, screenshots with personal data, or browser profiles.
- Reference requirement/phase identifiers in issues and commits when practical.
- Tag every presented release.

### Definition of done

A work item is done only when:

- acceptance criteria pass;
- relevant automated/manual tests pass;
- failure states are explicit;
- security/privacy/accessibility impacts were checked;
- telemetry/evidence is sufficient to diagnose it;
- documentation and progress evidence are updated;
- secrets and debug artifacts are absent; and
- another team member can explain or reproduce it.

### Work-session rhythm

1. Ten-minute status: yesterday, today, blocker.
2. Work only on the current phase's must-have items until its gate passes.
3. Integrate every coherent change through the lead environment.
4. End with a runnable main branch.
5. Update `ACCESSPATH_AI_PROGRESS_LOG.md` with evidence, not optimistic percentages.

---

## 12. Risk register for Phase 1

| Risk | Probability | Impact | Prevention | Triggered response |
|---|---|---|---|---|
| Limited team availability prevents completion of required phase gates | High | High | Assign ownership before Phase 1A; integrate continuously; avoid polish | Apply Section 7 cuts; preserve the controlled core |
| Gemini quota/network failure | Medium | High | Cache no secrets; keep deterministic adapter; rehearse | Disclose failure; use labeled contingency run/recording |
| Gemini loops or returns invalid actions | High | High | Structured output, Pydantic, budgets, policy | Reject, bounded retry, then inconclusive/planner error |
| Public site changes or blocks automation | High | Medium | Supporting target only; low budget; no claims | Remove from live demo; use recorded evidence if allowed |
| False completion on broken fixture | Medium | Critical | Deterministic completion oracle; repeated tests | NO-GO; fix before presentation |
| Celery/Playwright integration blocks the vertical slice | Medium | High | Prove Celery in Phase 1A and Playwright in Phase 1C | Cut public/axe/UI polish, not the worker boundary |
| Browser processes leak | Medium | High | Context manager, finally cleanup, timeouts | Stop repeated runs; repair cleanup |
| Secret exposure | Low | Critical | `.env`, redacted logs, limited prompt | Revoke key, purge history if needed, document incident |
| Fixture appears biased/artificial | Medium | Medium | Same accessible/broken task; public support run | Explain controlled ground truth and portability evidence |
| Team claims compliance from a demo | Medium | High | Required disclaimer and coverage language | Correct slides/report before review |

---

## 13. Project presentation package

Prepare these artifacts from the tagged revision:

- Working local application.
- Five-to-seven minute demo path, adjusted when presentation time is known.
- Architecture diagram showing AI proposal versus deterministic authorization/evidence.
- Accessible/broken fixture ground-truth table.
- Repetition results and known limitations.
- Screenshot/trace evidence for one completed and one blocked/inconclusive run.
- Progress table showing why Phase 0 + Phase 1 equals approximately 35%.
- Next-phase backlog and risk mitigation.
- Optional short backup recording if permitted.

Avoid spending implementation effort on a large slide deck before Gate 1E passes.

---

## 14. Immediate next actions

1. Record the exact review date and presentation duration as soon as they are issued.
2. Put team member names against Lead/Integration, AI/ML, and QA/Fixture/Documentation.
3. Rotate the credential disclosed in chat, configure the replacement locally, and re-run model/quota preflight before the live demo.
4. Freeze and tag the demonstrated revision after team review.
5. Prepare the synopsis/slides from the verified evidence registry and rehearse within the confirmed duration.
6. Begin Phase 2 only after the Phase 1 baseline is frozen; do not expand the Phase 1 demonstration scope.

---

## 15. Change log

| Version | Date | Summary |
|---|---|---|
| 1.3 | 27 September 2026 | Recorded the verified Gemini runtime configuration, visible contingency semantics, completed technical Phase 1 baseline, and post-Phase-1 release actions |
| 1.2 | 26 September 2026 | Added fixed fixture-server and KBD-001 specifications, immutable StepEvidence and ArtifactStore contracts, account-validated Gemini runtime limits, binding role/continuity rules, course-requirement acquisition, optional public-target proof, and gate-driven recovery controls |
| 1.1 | 25 September 2026 | Replaced time- and day-based scheduling with dependency-ordered development phases 1A–1F, each governed by deliverables, exit evidence, and GO/NO-GO gates |
| 1.0 | 25 September 2026 | Created the evidence-weighted course roadmap, initial Phase 1 execution sequence, autonomous keyboard vertical slice, scope cuts, review/improvement gates, later phases, testing plan, and risk controls |
