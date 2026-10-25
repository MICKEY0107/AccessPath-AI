# AccessPath AI project component status

**As of:** 28 September 2026  
**Basis:** Repository inspection plus the decision-grade evidence in `ACCESSPATH_AI_PROGRESS_LOG.md`  
**Progress basis:** Keyboard-first course delivery, not the larger lifetime multi-disability product vision

## Executive status

| Area | Status | Evidence-based interpretation |
|---|---|---|
| Phase 0 — plans, architecture, controls | Complete | Master plan, implementation plan, safety boundary, terminology, ownership roles, and evidence process exist. |
| Phase 1 — technical vertical slice | In review (95% of phase) | WP1–WP6 pass. WP7 waits for one uninterrupted post-fix 3+5 live-provider matrix, team rehearsal, and release tag. |
| Overall keyboard-first course delivery | 33.5% | 5% Phase 0 + 28.5% earned from the 30% Phase 1 allocation. |
| Later platform phases 2–6 | Not started, except foundations noted below | Local prototype seams exist, but their production/durable acceptance criteria have not been claimed. |

## Completed tasks

### Latest verified updates — 28 September 2026

- Added live filters for journey, planner, status, and outcome on Recent evaluation runs.
- Changed filtering to refresh only the results region, preserving the user's page position.
- Added clear accessible-reference and intentional-barrier messages to the two fixture journeys.
- Updated the blocked result explanation so it states plainly that keyboard focus cannot reach the appointment time buttons.
- Reseeded both fixture journeys after the behavior and deterministic fallback updates.
- Focused fixture, manifest, and run-view checks pass: 14 tests; Django system check passes.

### Planning, scope, and controls

- Defined the keyboard-only motor-accessibility profile, controlled-fixture boundary, result language, safety restrictions, completion policy, and evidence model.
- Defined the architecture, data direction, API/report roadmap, security/privacy requirements, evaluation method, phase weights, gates, risks, and ownership role IDs.
- Selected the controlled appointment booking as the guaranteed demonstration and kept public-target proof optional.
- Added an evidence-weighted progress log, defect register, decision register, review template, and exact eight-minute demo runbook.

### Runnable platform

- Created the Django application, semantic homepage, evaluation dashboard, run detail/report page, administration, migrations, PostgreSQL storage, Redis broker, and Celery worker.
- Containerized web, worker, PostgreSQL 18.6, Redis, and the fixture server with health checks and a shared run-artifact volume.
- Verified a clean `docker compose down` followed by `up -d --build`; all five services start and DB/Redis are healthy.
- Verified Celery connectivity with a live `pong`.

### Controlled journeys and product workflow

- Built versioned accessible and deliberately broken appointment-booking twins.
- Added fixed, approved journey presets and database seeding.
- Implemented run creation, worker execution, status/outcome persistence, recent-run display, step evidence, and screenshot evidence gallery.
- Added clear `Completed` versus `Blocked` language and explicit issue-evidence highlighting.
- Verified the dashboard, accessible detail, blocked detail, screenshot dialog, Escape close, and ArrowRight navigation in headed Chromium.

### Evaluation engine and safety boundary

- Implemented typed versioned contracts for observations, proposed actions, policy decisions, action results, step evidence, and run results.
- Implemented keyboard-only execution for Tab, Shift+Tab, Enter, Space, arrow keys, and bounded text entry.
- Made text entry idempotent with keyboard `Control+A` and replacement typing.
- Implemented deterministic policy authorization, origin restrictions, editable-target checks, action/rejection budgets, state fingerprints, completion checks, and browser cleanup.
- Persisted before/after focus, URL, action outcome, policy result, screenshots, and SHA-256 artifact metadata.
- Kept deterministic fixture planning as a visible, audited contingency rather than counting it as AI evidence.

### Gemini planning and resilience

- Implemented one-action-at-a-time structured Gemini planning with JSON Schema transport and server-side Pydantic validation.
- Added model discovery and semantic preflight scenarios, including null focus and wrong/non-editable focus.
- Added explicit focus/action prompt rules, minimum call pacing, timeout and transient retries, provider counters, and a bounded call limit.
- Ensured policy-rejected actions are recorded and never executed while permitting bounded Gemini replanning.
- Investigated `gemini-3.1-flash-lite`; preflight could pass, but journey behavior remained unreliable due to unusable focus proposals, policy rejection/call exhaustion, and intermittent upstream failures. The demonstrated local revision therefore uses account-discovered `models/gemini-3.5-flash-lite`.
- Proved one final no-fallback accessible completion: `af03b14a-6700-4b91-a437-b8e3ada1de83` (`completed`, 29 calls).
- Proved one final no-fallback broken control: `cf0e9180-6cd1-4d08-a7f1-972eba776d56` (`blocked`, 13 calls, `KEYBOARD_TARGET_NOT_REACHABLE`).

### Verification and documentation

- Added 40 automated tests covering contracts, policy, executor actions/safety, fixtures, views/services, Gemini client/planner/preflight, browser flow, and matrix command behavior.
- Passed the rebuilt-stack verification suite: 40 pytest tests, Ruff, Pyright, Django system check, migration-drift check, Celery ping, and service health.
- Updated README setup, model preflight, strict matrix, limits, fallback labeling, validation, and cleanup instructions.
- Prepared the exact demo path, speaking points, persisted proof IDs, outage contingency, hand-offs, and rehearsal pass criteria.

## Covered components

| Component | Coverage now | Boundary/limitation |
|---|---|---|
| Web UI | Homepage, journey cards, run list, outcome detail, evidence timeline, screenshot gallery | Local single-user UI; no accounts, team workspace, comparison view, or export. |
| Journey catalogue | One controlled multi-step appointment family with accessible and broken variants | Not yet representative of authentication, payment, messaging, uploads, recovery, or other families. |
| Keyboard profile | Real keyboard events, focus traversal/activation, bounded typing, focus evidence | Not the complete detector catalogue; composite widgets, traps, validation recovery, and restoration need systematic detector coverage. |
| Planner | Direct Gemini, selectable OpenRouter structured-action provider, plus deterministic test/contingency adapter | OpenRouter key/model are configured locally. Its live free route has shown temporary Nvidia overload and a length-limited completion. Provider results remain separately labelled and are never mixed as one evidence set. |
| Policy/safety | Action enum, target/origin checks, editable typing checks, budgets, rejected-action non-execution | Full SSRF/DNS/IP/redirect/egress hardening and object authorization are Phase 2. |
| Completion/barrier outcome | Deterministic completion oracle; declared broken barrier maps to Blocked | Only the controlled fixture contract is covered; broader detector precision/recall is unmeasured. |
| Evidence | Step/action/focus/state/policy data, before/after screenshots, digests, issue marker | Local/Compose volume only; no S3-compatible store, signed URLs, retention, redaction workflow, or exports. |
| Persistence and jobs | PostgreSQL run/evidence records and Celery execution | No transactional outbox, idempotent dispatch proof, leases/heartbeats, dead-letter admin, or crash recovery contract. |
| Quality | 48 unit/integration/browser tests, lint, static typing, framework/schema checks | No CI service, dependency/container/secret scanning, benchmark harness, or production smoke suite. |
| Operations | Rebuildable five-service local Compose stack | No staging deployment, TLS/domain, backups, managed services, production settings, or observability backend. |
| Documentation | Master/implementation plans, README, evidence/defect log, demo runbook, architecture/run-flow diagrams, and a presentation outline | Official rubric, team names, official demo duration, final slide deck, final report, demonstrated-revision commit, and release tag remain. |

## Missing or incomplete components

### Phase 1 exit items — required before claiming 35%

- Confirm the final evidence rule with the mentor: if Gemini-only is mandatory, pass and record an uninterrupted Gemini matrix; otherwise use one fixed preflight-verified live provider. In either case, run three accessible completions and five broken runs with zero false completions and no fallback counted as live evidence. The latest Gemini attempt passed its first two accessible cases (`617e664f-4769-487a-919e-5d6c395b5dc0`, `0ec08cd2-0406-4458-8e7d-c93a49227fc7`) and correctly failed case 3 when quota failure caused fallback (`4bb46fb5-8106-458f-90f2-0f0d47b06dd8`).
- Complete a second-person manual keyboard/product review and record the reviewer.
- Insert full team names, obtain the official presentation duration/rubric, rehearse to that duration, and finalize the presentation/slides.
- Commit the demonstrated baseline, hold the Phase 1 exit review, then create the release tag.
- Optional, not gate-blocking: approved read-only W3C BAD supporting run and separate axe-core baseline.

### Phase 2 — durable platform and security foundation (15%)

- Final normalized domain models for identities, projects, environments, credentials, findings, reports, artifacts, audit events, and coverage versions.
- Atomic run plus transactional outbox, idempotent dispatcher/delivery, worker claim semantics, retry scheduling, leases/heartbeats, cancellation, dead-letter handling, and restart/crash recovery tests.
- Local MinIO and S3-compatible artifact adapter, encrypted/scoped keys, signed authorized access, retention, deletion, and screenshot redaction.
- User authentication/OIDC decision and implementation, project membership, object-level authorization, and cross-tenant denial tests.
- Target ownership/authorization, URL normalization, DNS rebinding/private-IP/link-local/metadata blocking, redirect validation, browser egress controls, and stronger isolation.
- Structured logs, run correlation IDs, metrics, audit events, and operational dashboards.

### Phase 3 — keyboard evaluation breadth (20%)

- Versioned full keyboard profile and detector catalogue with applicability, evidence, and outcome rules.
- Ground-truth accessible/broken fixtures for reachability, activation, focus order, keyboard traps/escape, composite widgets, validation/error recovery, and focus restoration.
- Immutable reruns and result comparison, deterministic replay, loop detection/regression corpus, and broader origin/action/time/token budgets.
- Per-state axe-core baseline kept distinct from journey findings.
- Repeated-run agreement and pilot precision/recall/false-completion measurements against reviewed ground truth.

### Phase 4 — safe complete journeys and reporting (10%)

- At least one authenticated journey plus controlled registration, form, sandbox checkout/payment, messaging/upload, recovery, or account-management journeys.
- Fixture, observe-only, and sandbox-transactional execution modes.
- Opaque secret references resolved only inside workers.
- Typed sandbox adapters for payments, mail, messaging, and uploads; expected-effect assertions; cleanup verification and `cleanup_failed` handling.
- Versioned report schema, downloadable export, baseline/rerun comparison, coverage classifications, and precise limitations/disclaimer output.

### Phase 5 — evaluation and compliance traceability (10%)

- Frozen benchmark/corpus and protocol, two independent reviewers, adjudication, matched-state axe comparison, and tagged reproducibility package.
- Precision, recall, false completion, false block, inconclusive, agreement, latency, and model-cost analysis with raw confusion matrices.
- Error taxonomy and negative/ambiguous result analysis.
- Versioned WCAG 2.2 coverage register and applicable India/international mappings, with automatic/semi-automatic/manual/planned/not-applicable states.
- Academic results, limitations, literature positioning, and institution-approved report/rubric artifacts.

### Phase 6 — deployment, hardening, and final defense (10%)

- Approved staging platform with separate web/worker resources, managed data services, object storage, production configuration, health checks, TLS/domain, migrations, backups, retention, and recovery rehearsal.
- CI/CD gates for tests, lint/types, migrations, dependency/secret/static/container scans, image build, deployment, and smoke tests.
- OpenTelemetry-compatible traces/metrics/log correlation and error tracking.
- Repository-grounded threat model, security verification closure, privacy/data-governance checklist, incident/rotation procedures, and no open critical/high findings.
- Final tagged release, reproducible deployment documentation, final report, slides, architecture diagrams, evidence appendix, live demo, and approved backup evidence.

### Lifetime product vision — intentionally outside the keyboard-first course baseline

- Screen-reader/assistive-technology profiles with declared AT/browser combinations.
- Visual profiles for contrast, focus appearance, zoom/reflow, spacing, and non-text content.
- Hearing/multimedia, cognitive/learning, mobile web/native, document/PDF, native desktop, voice, switch, and other input profiles.
- Scheduled monitoring, CI integrations, external API/SDK ecosystem, enterprise reviewer workflows, and broader regulatory/procurement exports.

These are planned expansion areas, not current product claims. The present evidence supports a controlled keyboard-first journey evaluator—not whole-site accessibility or legal conformance.
