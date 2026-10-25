# AccessPath AI — Progress, Evidence, and Feedback Log

**Document role:** Living record of implementation status, evidence, feedback, and phase decisions  
**Version:** 1.10
**Created:** 25 September 2026  
**Current delivery phase:** Phase 1F — technical vertical slice in final evidence review
**Related documents:** `docs/planning/ACCESSPATH_AI_MASTER_PROJECT_PLAN.md`, `docs/planning/ACCESSPATH_AI_IMPLEMENTATION_PLAN.md`, `docs/PROJECT_COMPONENT_STATUS.md`, `docs/DEMONSTRATION_RUNBOOK.md`, `docs/ARCHITECTURE_AND_FLOW.md`, `docs/PRESENTATION_OUTLINE.md`, `docs/archive/PROJECT_HANDOFF_2026-09-28.md`

---

## 1. How to maintain this log

Update this file at the end of every work session and every phase review. Record what is demonstrably working, not what was attempted or how much time passed.

Rules:

- Never increase progress because files, lines of code, slides, or hours increased.
- Link progress to accepted criteria and evidence.
- Keep failed attempts and negative results when they affect decisions.
- Record commit/tag identifiers once Git exists.
- Never paste secrets, tokens, personal data, raw credentials, or unsafe target data.
- Put screenshots/traces in the configured artifact location and link their sanitized paths.
- Update the master plan only for product/architecture changes.
- Update the implementation plan when sequencing, scope, estimates, or phase gates change.

Status vocabulary:

- `NOT_STARTED`
- `IN_PROGRESS`
- `IN_REVIEW`
- `BLOCKED`
- `DONE`
- `DEFERRED`

---

## 2. Current snapshot

**Last updated:** 28 September 2026  
**Implementation status:** `IN_REVIEW`
**Planning status:** `DONE`  
**Current evidence-backed course progress:** 33.5%
**Target after Phase 1 exit review:** 35% after all Phase 1 exit criteria pass  
**Current release/tag:** Demonstrated revision will be committed after this review; release tag waits for the full Phase 1 gate
**Current primary blocker:** The final uninterrupted post-fix live-provider matrix has not passed as one command. The Gemini attempt completed two accessible cases without fallback, then correctly failed when case 3 hit Gemini quota and activated contingency. Gemini remains quota constrained; `openrouter/free` showed one Nvidia temporary-overload response and one length-limited completion. A 15–20 second interval did not turn either issue into an HTTP 429 key-rate-limit failure. The project now prevents an interval reset between consecutive runs in the same worker process, but a preflight-verified fixed live model is still required for the final matrix. Individual no-fallback accessible and broken Gemini proofs pass, and the historical 3+5 set remains valid, but history is not accepted as the final post-fix gate. Full team names, exact presentation duration, official rubric evidence, and a demonstrated-revision commit remain team records.
**Next gate:** Confirm whether the mentor requires Gemini-only evidence or accepts one fixed, preflight-verified live provider; then pass and record one provider-pure 3 accessible + 5 broken matrix with zero false completions, hold the exit review, commit, and tag the demonstrated revision.

The 33.5% is evidence-weighted: Phase 0 contributes 5%, and Phase 1 contributes 28.5% of its 30% allocation because WP1–WP6 are complete while the 5%-of-Phase-1 release/repetition package remains in review. This deliberately does not award the final 1.5 course-percentage points until the uninterrupted post-fix matrix and exit review pass.

---

## 3. Confirmed decisions

| ID | Date | Decision | Reason/source | Consequence |
|---|---|---|---|---|
| DEC-001 | 25 Sep 2026 | Keyboard-only motor accessibility is the first implementation profile | Team direction and master plan | Visual/audio/AT profiles remain later scope |
| DEC-002 | 25 Sep 2026 | Django Python-first modular monolith with separate Celery worker | Approved master technology stack | No React/FastAPI split in the initial implementation |
| DEC-003 | 25 Sep 2026 | The initial implementation runs locally; deployment is deferred | Team decision | Use local PostgreSQL and Redis; hosting begins only in the later deployment phase |
| DEC-004 | 25 Sep 2026 | The primary journey is a multi-step appointment-style task | Team decision | Build accessible and broken controlled twins |
| DEC-005 | 25 Sep 2026 | Gemini autonomous navigation is part of the initial target | Team decision | Planner remains bounded by policy and deterministic evidence |
| DEC-006 | 25 Sep 2026 | Controlled fixture is the guaranteed demo; public evaluation is supporting evidence | Safety and reproducibility review | No dependence on an unauthorized production transaction |
| DEC-007 | 25 Sep 2026 | Authentication/login/signup are outside the initial scope | Team decision | Defer OIDC and multi-user flows until platform hardening |
| DEC-008 | 25 Sep 2026 | Use W3C BAD as optional supporting proof; Deque MarsCommuter is stretch-only | Primary-source target research | Controlled fixture remains the only required proof; public runs are navigation/focus-only |
| DEC-009 | 26 Sep 2026 | Bind ownership to `LEAD_INTEGRATION`, `AI_ML`, and `QA_FIXTURE` role IDs | Gap remediation | Every task and safety review has one accountable role; full names are added before first shared merge |
| DEC-010 | 26 Sep 2026 | Pin PostgreSQL 18.6 and Celery 5.6.3 after local compatibility verification | Official release verification | No pre-release or floating dependency is accepted |
| DEC-011 | 26 Sep 2026 | Persist run artifacts in a Compose-managed shared volume mounted by web and worker | Non-root Docker verification on Windows bind mounts | Screenshot evidence survives worker execution without granting the app root access |
| DEC-012 | 28 Sep 2026 | Let the evaluator explicitly choose Gemini, OpenRouter, or deterministic mode from one dropdown | Provider reliability investigation | Provider and model are persisted with the run; no provider is silently substituted |
| DEC-013 | 28 Sep 2026 | Apply provider pacing across newly constructed clients in one worker process | Consecutive runs previously reset the per-client interval | The Compose worker stays at concurrency one and the process-wide gate protects the boundary between runs |

---

## 4. Open decisions

| ID | Decision needed | Owner | Required by | Status | Resolution |
|---|---|---|---|---|---|
| OPEN-001 | Exact presentation date and duration | Team/mentor | Before Gate 1F | OPEN | — |
| OPEN-002 | Full names recorded against binding role IDs | LEAD_INTEGRATION | Before first shared merge | OPEN | Role assignments are fixed below; names must be added without changing accountability |
| OPEN-003 | Approved supporting public target | Whole team | Before Phase 1E | RESOLVED | W3C BAD; Deque MarsCommuter only if required phases are stable |
| OPEN-004 | Whether a prerecorded backup is permitted | Team/mentor | Before Gate 1F | OPEN | — |
| OPEN-005 | Exact Gemini model identifier available to the free API key | AI/ML | During Phase 1D | RESOLVED | Account discovery and structured-output preflight passed for `models/gemini-3.5-flash-lite` on 27 Sep 2026; re-preflight because availability is time/account specific |
| OPEN-006 | Whether the final 3+5 gate is Gemini-only or provider-neutral | Team/mentor | Before final live matrix | OPEN | UI supports Gemini and OpenRouter; evidence must remain provider-pure either way |

### Binding team roster

| Role ID | Assigned contributor | Backup | Accountabilities |
|---|---|---|---|
| `LEAD_INTEGRATION` | Project initiator/local development-machine operator | `AI_ML` | Django, Compose, database, Celery, integration, release tag |
| `AI_ML` | Teammate responsible for AI/ML work | `LEAD_INTEGRATION` | Gemini planner, structured output, prompt/policy tests, quota preflight |
| `QA_FIXTURE` | Remaining teammate | `LEAD_INTEGRATION` | Fixture ground truth, manual keyboard verification, evidence, presentation documentation |

No task may list “whole team” as its sole owner. Contributors add their full names in this table before the first shared merge.

### Course-requirements register — resolves TP-005

| Requirement ID | Institutional source | Deliverable | Owner | Required phase/gate | Status | Evidence/location |
|---|---|---|---|---|---|---|
| COURSE-001 | BML Munjal rubric/mentor instruction | Synopsis/proposal format and submission | `QA_FIXTURE` | Before proposal submission | PENDING_INSTITUTION | — |
| COURSE-002 | BML Munjal rubric/mentor instruction | Internal review criteria | `QA_FIXTURE` | Before Gate 1F | PENDING_INSTITUTION | — |
| COURSE-003 | BML Munjal rubric/mentor instruction | Final report template, page rules, and references | `QA_FIXTURE` | Before Phase 5 closes | PENDING_INSTITUTION | — |
| COURSE-004 | BML Munjal rubric/mentor instruction | Presentation/viva duration, scoring, and submission requirements | `QA_FIXTURE` | Before Gate 1F and Phase 6 | PENDING_INSTITUTION | — |

The team must obtain the official source or a written mentor instruction and replace `PENDING_INSTITUTION` with dated evidence. No institutional requirement may be invented from a generic project template.

---

## 5. Evidence-weighted phase scorecard

Do not mark a phase complete unless its exit review is `GO` or `CONDITIONAL GO` under the implementation plan.

| Phase | Weight | Status | Earned | Exit review | Evidence reference |
|---|---:|---|---:|---|---|
| Phase 0 — Planning and controls | 5% | DONE | 5% | GO | Master plan + implementation plan |
| Phase 1 — Technical vertical slice | 30% | IN_REVIEW | 28.5% | Not held after final fixes; fresh uninterrupted matrix pending | EVD-006 through EVD-015; automated tests |
| Phase 2 — Durable platform/security | 15% | NOT_STARTED | 0% | Not held | — |
| Phase 3 — Keyboard evaluation breadth | 20% | NOT_STARTED | 0% | Not held | — |
| Phase 4 — Safe complete journeys/reporting | 10% | NOT_STARTED | 0% | Not held | — |
| Phase 5 — Evaluation/compliance | 10% | NOT_STARTED | 0% | Not held | — |
| Phase 6 — Deployment/final defense | 10% | NOT_STARTED | 0% | Not held | — |
| **Total** | **100%** |  | **33.5%** |  |  |

### Phase 1 internal readiness

This table shows readiness inside the phase; it does not add to overall progress until the vertical slice passes its exit gate.

| Work package | Phase-1 weight | Status | Owner | Acceptance evidence |
|---|---:|---|---|---|
| WP1 — Repository, Django, PostgreSQL, Redis/Celery | 15% | DONE | Lead | Compose services healthy; migrations applied; Celery worker ready |
| WP2 — Homepage and product navigation | 10% | DONE | Lead + QA | `/runs/` dashboard/detail UI validated over HTTP and browser snapshot; provider dropdown is keyboard-accessible |
| WP3 — Accessible/broken appointment fixtures | 15% | DONE | QA/Fixture | Controlled twins served on fixture origin; CLI keyboard review completed |
| WP4 — Observer, policy, keyboard executor, completion oracle | 25% | DONE | Lead | 21-step completion and 5-step barrier evidence runs |
| WP5 — Live planner and safety tests | 20% | DONE | AI/ML | Typed Gemini and OpenRouter output, server validation, policy gate, safe fallback, Gemini discovery/preflight, and OpenRouter preflight diagnostics |
| WP6 — Progress/report UI and evidence | 10% | DONE | Lead + QA | Persisted step evidence, SHA-256 artifacts, run outcome page; fresh live evidence in EVD-004/EVD-005 |
| WP7 — Repetition tests, rehearsal, and tagged demo | 5% | IN_REVIEW | Whole team | Individual final proofs and clean rehearsal pass; uninterrupted post-fix 3+5 matrix, timed team rehearsal, and release tag remain |

---

## 6. Phase 1 development phase board

### Phase 1A — Project foundation and runnable platform

**Status:** `DONE`  
**Objective:** Runnable Django/PostgreSQL/Redis/Celery foundation and homepage  
**Gate 1A result:** `GO` — local Compose stack and quality commands verified

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Assign role names | Team | IN_PROGRESS | Role IDs recorded; full names remain open | — |
| Initialize repository and pinned Python environment | Lead | DONE | `pyproject.toml`, `uv.lock`, Python 3.13 | — |
| Create Django settings/project | Lead | DONE | Django apps, settings, URLs, templates | — |
| Start PostgreSQL and Redis locally | Lead | DONE | Compose services healthy | — |
| Execute Celery test task | Lead | DONE | Worker registered and processed live runs | — |
| Create semantic homepage/navigation | Lead + QA | DONE | `/` and `/runs/` validated over HTTP/UI | — |
| Configure Ruff/Pyright/pytest | Lead | DONE | Quality gates pass | — |
| Pin PostgreSQL 18.6/Celery 5.6.3 and record compatibility evidence | Lead | DONE | Compose and lockfile verified | No pre-release/floating version |
| Create remote, `.gitignore`, `.env.example`, and recovery runbook | Lead | IN_PROGRESS | Local Git/docs/runbook complete; remote is not required for local development | Second member must clean-setup |
| Obtain/register official course requirements | QA/Fixture | PENDING_INSTITUTION | Rubric evidence still needs mentor/course confirmation | Do not infer rubric requirements |

**Phase result:** `GO` — foundation and local controls are runnable.  
**Feedback received:** Windows bind mounts required an anonymous virtualenv volume and a managed artifact volume.  
**Improvements applied/deferred:** Non-root Docker runtime applied; remote repository and institutional rubric evidence remain open.  
**Next phase action:** Maintain the foundation while closing Phase 1B review items.

### Phase 1B — Controlled journey and ground truth

**Status:** `DONE`  
**Objective:** Accessible and deliberately broken appointment twins with reviewed ground truth  
**Gate 1B result:** `GO` — accessible and broken controlled fixtures verified

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Build accessible AccessPath Clinic fixture | QA/Fixture + Lead | DONE | Versioned fixture manifest and pages | — |
| Build broken twin with one declared barrier | QA/Fixture | DONE | Broken slot control verified | — |
| Define task, synthetic data, and completion signal | Whole team | DONE | Manifest completion oracle and synthetic values | — |
| Complete two-person manual keyboard review | QA + AI/ML | IN_PROGRESS | CLI review completed by lead; second reviewer pending | — |
| Create fixed-target run form | Lead | DONE | DB-backed journey choices on `/runs/` | — |

**Phase result:** `GO` — accessible and broken controlled twins have reviewed ground truth.  
**Feedback received:** Barrier control must report the actual executed step count.  
**Improvements applied/deferred:** Step-count tracking fixed; second-person manual review remains.  
**Next phase action:** Keep fixtures stable while extending planner coverage.

### Phase 1C — Deterministic keyboard evaluation kernel

**Status:** `DONE`  
**Objective:** Policy-controlled Playwright keyboard execution and evidence without AI  
**Gate 1C result:** `GO` — keyboard-only executor and persisted evidence verified

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Define engine contracts | Lead + AI/ML | DONE | Versioned Pydantic contracts | — |
| Implement observer | Lead | DONE | Focus/state fingerprints in executor evidence | — |
| Implement policy validator | Lead | DONE | Keyboard action policy and rejection budget | — |
| Implement keyboard executor | Lead | DONE | Playwright keyboard-only executor | — |
| Implement deterministic adapter/oracle | Lead + QA | DONE | `fixture_plan.v1` and completion stability checks | — |
| Run from Celery and persist evidence | Lead | DONE | Live runs EVD-004/EVD-005 | — |

**Phase result:** `GO` — deterministic keyboard execution and persisted evidence are live.  
**Feedback received:** ORM writes inside the browser callback were unsafe in Celery.  
**Improvements applied/deferred:** Evidence is buffered during Playwright execution and persisted transactionally afterward.  
**Next phase action:** Add bounded Gemini proposal generation behind the existing Planner seam.

### Phase 1D — Bounded autonomous Gemini planner

**Status:** `IN_REVIEW`  
**Objective:** Model proposes typed actions while deterministic policy remains authoritative  
**Gate 1D result:** `IN_REVIEW` — typed planner, semantic preflight, policy control, and individual live proofs pass; final repetition gate is pending

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Verify available current Gemini model | AI/ML | DONE | API discovery + EVD-006 | `models/gemini-3.5-flash-lite` passed; no guessed identifier |
| Implement Planner interface/Gemini adapter | AI/ML | DONE | `engine/planner.py`, `engine/gemini.py` | One bounded proposal per observation |
| Add structured output and Pydantic validation | AI/ML + Lead | DONE | Provider JSON Schema + `ProposedActionV1` server validation | Extra/unsafe fields rejected |
| Record quota preflight and planner runtime configuration | AI/ML | DONE | EVD-006; `.env.example` | Semantic preflight passed; 40-attempt/timeout/retry limits documented |
| Add injection/policy-violation fixtures | AI/ML + QA | DONE | Automated unsafe, malformed, invalid-origin, invalid-target, timeout, recovery, and executor tests | 40-test suite |
| Measure repeated accessible/broken runs | Whole team | IN_REVIEW | EVD-007/EVD-008 historical; EVD-012/EVD-013 final individual proofs; EVD-014 strict attempts | Fresh uninterrupted 3+5 command is still required |

**Phase result:** `IN_REVIEW`  
**Feedback received:** Strict reruns exposed semantically unusable proposals, policy-rejection fallback, timeout retry handling, append-only typing, and intermittent provider 5xx/504 behavior.  
**Improvements applied/deferred:** Semantic preflight, stronger focus rules, bounded Gemini replanning after policy rejection, timeout retries, idempotent field replacement, provider counters, and consistent call/step budgets were applied and retested.  
**Next phase action:** Accept only a fresh uninterrupted strict matrix with no fallback as the final repetition gate.

### Phase 1E — Product workflow, reporting, and portability proof

**Status:** `IN_PROGRESS`  
**Objective:** Complete UI-driven local workflow and safe supporting public proof  
**Gate 1E result:** Not held — deterministic local workflow is working; public supporting proof is deferred

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Complete create/progress/report views | Lead | DONE | Dashboard, run detail, outcome, evidence links | — |
| Present step/focus/screenshot evidence | Lead + QA | DONE | Fresh live runs show step and artifact evidence | — |
| Run product keyboard/accessibility review | QA | IN_PROGRESS | Lead CLI review complete; second reviewer pending | — |
| Test W3C BAD with reviewed read-only manifest | Whole team | NOT_STARTED | — | Deque MarsCommuter is stretch-only |
| Add end-to-end smoke test | Lead | DONE | Browser fixture integration tests included in 10-test suite | — |

**Phase result:** —  
**Feedback received:** —  
**Improvements applied/deferred:** —  
**Next phase action:** —

### Phase 1F — Verification, review, and demonstrated release

**Status:** `IN_REVIEW`  
**Objective:** Tagged, repeatable, evidence-backed demonstration  
**Gate 1F result:** Not held — rebuilt-stack verification and browser rehearsal pass; final strict matrix and team release records remain

| Deliverable | Owner | Status | Evidence/commit | Notes/blocker |
|---|---|---|---|---|
| Freeze features and run quality suite | Lead | DONE | 48 tests, Ruff, Pyright, Django checks, schema drift clean | Latest Docker verification on 28 Sep 2026 |
| Run repetition matrix | Whole team | IN_REVIEW | EVD-007/EVD-008 historical; EVD-014 fresh attempts | Final post-fix 3+5 command must pass without fallback |
| Fix P0/P1 issues | Assigned at review | DONE | DEF-006 through DEF-013 | Focused and full suites pass |
| Complete slides/demo script/limitations | QA + Whole team | IN_PROGRESS | Demo runbook, architecture diagrams, and seven-slide outline | Team duration, names, and final slide deck remain |
| Perform two clean rehearsals | Whole team | DONE | Prior rehearsal plus EVD-015 clean rebuild/browser run | Browser flow validated in headed Chromium |
| Create and record release tag | Lead | NOT_STARTED | — | Commit the demonstrated revision now; tag only after the gate passes |

**Phase result:** `IN_REVIEW` for the technical foundation.  
**Feedback received:** Provider availability is intermittent, and historical successes must not substitute for the post-fix exit gate.  
**Improvements applied/deferred:** The deterministic contingency remains visible, the exact browser demonstration flow is documented, and a clean rebuild passes. Complete the strict matrix, obtain the official duration, add team names, then tag.  
**Next phase action:** Record the running/final strict matrix result, rehearse to the official duration, hold the exit review, and create the release tag.

---

## 7. Test and evidence registry

Add one row for every decision-grade test run. Do not place raw model secrets or personal data here.

| Evidence ID | Date/time | Revision | Target/variant | Planner | Goal | Expected | Actual | Pass? | Artifact reference |
|---|---|---|---|---|---|---|---|---|---|
| EVD-001 | 26 Sep 2026 | Working tree | Accessible clinic fixture | `fixture_plan.v1` | Complete synthetic appointment using keyboard only | Completion policy satisfied | `completed`, 21 steps, screenshots persisted | PASS | Run `eba29182-fefa-418f-ad55-7c55b014d281` |
| EVD-002 | 26 Sep 2026 | Working tree | Broken clinic fixture | `fixture_plan.v1` | Detect keyboard barrier at appointment slot | Must not false-complete | `blocked`, `KEYBOARD_TARGET_NOT_REACHABLE`, 5 steps | PASS | Run `3e59510d-8397-41bc-bdcb-65f17edbf9c0` |
| EVD-003 | 26 Sep 2026 | Working tree | Local quality suite | N/A | Prevent regression | Tests/lint/types pass | 10 tests passed; Ruff and Pyright clean | PASS | `uv run pytest -q`, `uv run ruff check .`, `uv run pyright` |
| EVD-004 | 26 Sep 2026 | Working tree | Accessible clinic fixture, hardened Compose runtime | `fixture_plan.v1` | Re-run the primary demo after non-root/artifact-volume hardening | Completion policy satisfied and screenshots served | `completed`, 21 steps, 42 screenshot links, `COMPLETION_POLICY_SATISFIED` | PASS | Run `8862d69f-cae1-410c-9c08-e7b773e880b3` |
| EVD-005 | 26 Sep 2026 | Working tree | Broken clinic fixture, hardened Compose runtime | `fixture_plan.v1` | Re-run the negative control after hardening | Must block at unreachable appointment slot and report actual steps | `blocked`, `KEYBOARD_TARGET_NOT_REACHABLE`, 5 steps, 10 screenshot links | PASS | Run `a0cd1382-5730-44aa-85bf-7537f0d6b8b3` |
| EVD-006 | 27 Sep 2026 | Working tree | Gemini account/model preflight | `gemini.v1` | Discover rather than guess a model and verify typed structured calls | Exact advertised model and three paced calls pass | `models/gemini-3.5-flash-lite`; 3/3 calls passed at 15-second interval | PASS | `preflight_gemini` command output; no credential persisted |
| EVD-007 | 27 Sep 2026 | Working tree | Accessible clinic repetition matrix | `gemini.v1` | Complete the controlled appointment journey autonomously | 3 live-model completions; no fallback | 3/3 `completed`; call counts 23, 23, 24; `fallback_used=false` | PASS | Runs `b7e63b59-2b45-4887-9b57-70e889d936a9`, `811aabab-a695-4244-bfaf-041c58c9909f`, `98c176cc-4a84-44c6-afaa-751b63cd5e62` |
| EVD-008 | 27 Sep 2026 | Working tree | Broken clinic repetition matrix | `gemini.v1` | Detect the declared keyboard barrier without false completion | 5 blocked; 0 false completions; no fallback | 5/5 `blocked`; 0 `completed`; `fallback_used=false` | PASS | Runs `4a0d2c28-ac2a-4c90-be17-3a0736d98058`, `ad12bc85-1bfb-488b-b89c-b18cd33ce85e`, `cf0df8d5-239e-443c-8699-63a606760447`, `9be3cd11-f258-47a8-ba22-224003f68e3b`, `fd89501b-057e-460b-af6f-8312117f9073` |
| EVD-009 | 27 Sep 2026 | Working tree | Final local quality suite | N/A | Prevent regression after Gemini/recovery changes | Tests, lint, types, framework and schema checks pass | 32 tests passed; Ruff and Pyright clean; Django and migration checks clean | PASS | Validation commands in README |
| EVD-010 | 27 Sep 2026 | Working tree | Clean rebuilt Docker/UI rehearsal | `fixture_plan.v1` contingency | Prove fresh stack, Celery workflow, visible contingency, evidence UI, and gallery keyboard control | Healthy stack and completed evidence-backed journey | 5 services up; DB/Redis healthy; Celery pong; run completed in 21 steps; 42 screenshots; ArrowRight advanced gallery | PASS | Run `3544ccfe-0fd4-4f47-ace8-1a035c51eb95` |
| EVD-011 | 27 Sep 2026 | Working tree | `models/gemini-3.1-flash-lite` diagnostic runs | `gemini.v1` | Determine whether 504s were the only cause of unreliable completion | Useful typed actions and no fallback | Preflight could pass, but journey runs repeatedly produced unusable focus actions, policy rejection, call-limit fallback, and intermittent upstream failure | FAIL — model not selected for the demonstrated revision | Runs `f67c84fd-d455-401b-8cf2-a5a467060a57`, `d1e02f1c-02d4-479f-864f-8f737e54dd66`, `3d50b042-c000-4f63-bc6e-fc94f3da3bb9`, `35714f4d-16c7-4918-8415-025f26ee3b14` |
| EVD-012 | 27 Sep 2026 | Working tree | Accessible clinic after semantic/retry/executor fixes | `gemini.v1`, `models/gemini-3.5-flash-lite` | Prove one complete accessible booking without deterministic fallback | `completed`, live Gemini only | `completed`, 29 provider calls, `fallback_used=false`, completion policy satisfied | PASS | Run `af03b14a-6700-4b91-a437-b8e3ada1de83` |
| EVD-013 | 27 Sep 2026 | Working tree | Broken clinic after planner fixes | `gemini.v1`, `models/gemini-3.5-flash-lite` | Prove the declared barrier is classified without false completion or fallback | `blocked`, live Gemini only | `blocked`, 13 provider calls, `fallback_used=false`, `KEYBOARD_TARGET_NOT_REACHABLE` | PASS | Run `cf0e9180-6cd1-4d08-a7f1-972eba776d56` |
| EVD-014 | 27–28 Sep 2026 | Working tree | Fresh strict matrix attempts | `gemini.v1`, `models/gemini-3.5-flash-lite` | Pass one uninterrupted 3 accessible + 5 broken command after all fixes | 8/8 valid, no fallback, zero false completion | Latest attempt passed accessible cases 1–2 without fallback, then correctly failed case 3 because Gemini quota failure activated fallback; earlier attempts exposed now-fixed timeout and append-only typing defects | FAIL — gate remains open | Latest: `617e664f-4769-487a-919e-5d6c395b5dc0` (pass, 33 calls), `0ec08cd2-0406-4458-8e7d-c93a49227fc7` (pass, 25 calls), `4bb46fb5-8106-458f-90f2-0f0d47b06dd8` (fallback after quota failure). Earlier: `0423a5b3-6260-4567-9211-99bd5fad61a3`, `61c6cb13-19f7-42d8-b3a3-2b3b24795cf2`, `82ce8472-6703-43db-b0a2-f878d55a5967`, `73d1bd42-2a41-4114-9a29-b37eb5aa9ca6`, `0eea8661-40e0-469e-84da-78028d986a61` |
| EVD-015 | 28 Sep 2026 | Working tree | Latest Docker verification and headed-browser review | N/A | Verify regressions and the provider-selection UI | Healthy five-service stack; accessible provider dropdown; quality suite clean | 48 tests passed; Ruff/Pyright/Django/schema checks clean; dashboard browser snapshot showed two accessible comboboxes with no radio controls | PASS | Local browser snapshot and current Compose services |
| EVD-016 | 28 Sep 2026 | Working tree | OpenRouter provider integration and live diagnosis | `openrouter.v1` | Offer an explicitly selectable alternate live planner without mixing provider evidence | Provider/model persisted per run; strict JSON request; semantic preflight; provider-specific matrix command; response diagnostics; cross-run pacing | OpenRouter `openrouter/free` returned one Nvidia temporary-overload response at a 20-second interval and one length-limited completion. No HTTP 429 was observed. 48 tests passed after the pacing/UI update. | PASS — implementation verification; LIVE MATRIX PENDING | `engine/openrouter.py`, `engine/pacing.py`, `preflight_openrouter`, dashboard dropdown |

### Repetition summary

| Metric | Required | Current | Status |
|---|---:|---:|---|
| Consecutive accessible-fixture completions using Gemini | 3 | Historical 3/3 exists; final post-fix uninterrupted command is pending | NOT YET — EVD-014 |
| Broken-fixture repeated runs | 5 | Historical 5/5 exists; final post-fix command is pending | HISTORICAL PASS; FINAL GATE PENDING |
| False completion on broken fixture | 0 | 0 | PASS |
| Executed actions outside keyboard schema | 0 | 0 | PASS — enum/schema and policy enforced |
| Unsafe proposed action executed | 0 | 0 | PASS — rejection tests and evidence verified |
| Successful clean-start rehearsals | 2 | 2 | PASS — prior rehearsal plus clean rebuild EVD-015 |

---

## 8. Feedback and improvement register

| Feedback ID | Date | Source | Observation/request | Priority | Decision | Owner | Verification/evidence | Status |
|---|---|---|---|---|---|---|---|---|
| UI-001 | 27 Sep 2026 | Project lead | Make application navigation presentation-ready; explain runs briefly; enable keyboard review of screenshots; visibly identify issue evidence | P2 | ACCEPT | LEAD_INTEGRATION | Live blocked run `652cad6d-8121-4529-80f2-f657f8b99599`; arrow-key gallery and red issue card validated | DONE |

Decision values: `ACCEPT`, `MODIFY`, `DEFER`, or `REJECT_WITH_REASON`.

---

## 9. Blocker and defect register

| Item ID | Found | Description | Severity | Owner | Workaround | Target resolution | Status |
|---|---|---|---|---|---|---|---|
| DEF-001 | 26 Sep 2026 | Django ORM writes from a Playwright callback raised `SynchronousOnlyOperation` in Celery | P1 | Lead | Buffer evidence in memory during browser execution | Phase 1C | FIXED; verified by live run EVD-001/EVD-002 |
| DEF-002 | 26 Sep 2026 | PostgreSQL 18 rejected legacy `/var/lib/postgresql/data` volume target | P1 | Lead | Versioned volume and major-version mount | Phase 1A | FIXED; DB healthy |
| DEF-003 | 26 Sep 2026 | Windows bind mount hid Linux `.venv`, so Celery executable was missing | P1 | Lead | Anonymous `/app/.venv` volume | Phase 1A | FIXED; worker healthy |
| DEF-004 | 26 Sep 2026 | Broken-run result reported max step budget rather than actual executed steps | P2 | Lead | Return tracked `steps_run` | Phase 1C | FIXED; reports 5 steps |
| DEF-005 | 26 Sep 2026 | Non-root containers could not write screenshots through the Windows source bind mount | P1 | Lead | Shared Compose-managed `run_output` volume | Phase 1A | FIXED; fresh live runs EVD-004/EVD-005 persist artifacts |
| DEF-006 | 27 Sep 2026 | Provider rejected Pydantic schema through the limited `response_schema` field (`additional_properties` unsupported) | P1 | AI/ML + Lead | Use SDK `response_json_schema` and retain server Pydantic validation | Phase 1D | FIXED; EVD-006 passed |
| DEF-007 | 27 Sep 2026 | Form input changes were absent from state fingerprints; contingency resumed by action count after AI divergence | P1 | Lead | Hash local form state; restart contingency once at allowlisted start URL | Phase 1D | FIXED; browser regression tests and EVD-007 passed |
| DEF-008 | 27 Sep 2026 | Intermittent provider 503/504 responses exceeded the original timeout/recovery margins | P1 | AI/ML + Lead | Five bounded 5xx/timeout retries, 40 provider attempts, 30-second timeout, 56 executed-step total budget, and explicit failure counters | Phase 1D | FIXED/CONTROLLED; retry behavior passes tests, while provider availability/quota remains external (EVD-014) |
| DEF-009 | 27 Sep 2026 | Schema-only preflight accepted semantically unusable actions such as Enter with no focused element | P1 | AI/ML + Lead | Add null-focus and wrong-focus semantic scenarios plus explicit focus/action rules | Phase 1D | FIXED; semantic preflight and focused tests pass |
| DEF-010 | 27 Sep 2026 | One policy-rejected Gemini proposal immediately switched the run to deterministic fallback | P1 | Lead | Record and reject the proposal, then allow another bounded Gemini turn | Phase 1D | FIXED; rejection remains unexecuted and recovery test passes |
| DEF-011 | 27 Sep 2026 | Provider timeout bypassed the configured transient retry budget | P1 | AI/ML + Lead | Route timeout through the same bounded retry path as transient 5xx failures | Phase 1D | FIXED; timeout retry test passes |
| DEF-012 | 27 Sep 2026 | Repeated Type proposals appended duplicate text, invalidated the form, and consumed the call budget | P1 | Lead | Implement keyboard-only idempotent replacement with Control+A followed by typing | Phase 1D | FIXED; executor regression test and EVD-012 pass |
| DEF-013 | 28 Sep 2026 | Fixture manifest test hard-coded the host origin while Compose correctly uses the `fixture` service origin | P2 | Lead | Derive expected origin from `FIXTURE_ALLOWED_ORIGINS` | Phase 1F | FIXED; full 40-test rebuilt-stack suite passes |

Severity:

- `P0`: safety, secret exposure, data loss, unauthorized effect, or unusable demo.
- `P1`: false core result, policy bypass, or broken primary workflow.
- `P2`: important quality/accessibility/maintainability weakness.
- `P3`: improvement or future scope.

---

## 10. Phase review record

Copy this subsection for each phase review.

### Phase review: [phase and date]

**Decision:** `GO | CONDITIONAL_GO | NO_GO`  
**Revision/tag reviewed:** —  
**Participants:** —

#### Acceptance criteria

- [ ] Required user outcome demonstrated.
- [ ] Automated tests pass.
- [ ] Manual keyboard/product accessibility check passes.
- [ ] Relevant security/privacy/safety checks pass.
- [ ] Evidence and metrics are recorded.
- [ ] Known limitations are documented.
- [ ] P0/P1 issues are closed.
- [ ] P2/P3 items have owners or backlog decisions.

#### Evidence reviewed

- —

#### Feedback and decisions

- —

#### Required improvements before next phase

- —

---

## 11. Demonstration readiness

### Product

- [x] Homepage accurately explains the keyboard-first project.
- [x] New-run screen uses fixed approved task/target choices.
- [x] Accessible fixture completes through keyboard-only actions.
- [x] Broken fixture does not false-complete.
- [x] Gemini proposes actions through the typed Planner interface.
- [x] Policy rejects unsupported/unsafe proposals.
- [x] Progress and report are visible in the Django UI.
- [x] Evidence supports the final outcome.

### Reliability and safety

- [x] Local PostgreSQL, Redis, Celery, Django, and Chromium start from documented commands.
- [x] Time/action limits prevent endless runs.
- [x] Browser cleanup works after success and failure.
- [x] No secret or personal data is committed or displayed.
- [ ] Public target, if used, is approved and read-only.
- [x] Contingency adapter/recording is clearly labeled.
- [ ] One uninterrupted post-fix 3-accessible/5-broken live-Gemini matrix passes with no fallback.

### Presentation

- [ ] Exact duration is known and rehearsal fits it.
- [x] Architecture explains AI versus deterministic control.
- [x] Progress percentage is backed by phase evidence and held below 35% until the final gate passes.
- [x] Limitations and deferred scope are shown.
- [x] Two clean rehearsals pass.
- [ ] Demonstrated revision is committed; release tag follows the final exit gate.

---

## 12. Work-session entry template

### Work session — 27–28 September 2026

```text
Participants: LEAD_INTEGRATION with Codex implementation support
Planned outcome: Close the Phase 1 technical checklist and correct unsupported completion claims.
Work completed: Diagnosed Gemini 3.1 behavior; added semantic preflight and focus rules; kept policy rejection under bounded Gemini replanning; retried timeouts; made Type idempotent; added provider counters and regression tests; proved one no-fallback accessible completion and one no-fallback blocked control; rebuilt Docker from down state; fixed the Compose-origin test; manually reviewed the dashboard and both outcomes in headed Chromium; prepared the exact demo runbook.
Acceptance checks run: 40 pytest tests, Ruff, Pyright, Django check, migration drift check, Celery ping, Compose health, headed-browser semantic/layout/gallery review.
Evidence/commit/artifacts: EVD-011 through EVD-015; commit identifier to be inserted after commit.
Unexpected result or blocker: Gemini 3.1 preflight success did not predict useful journey behavior; Gemini 3.5 strict reruns exposed timeout and repeated-typing defects. A fresh uninterrupted post-fix 3+5 matrix remains the only technical exit-gate item.
Feedback received: Historical runs and individual proofs must be separated from the final post-fix strict gate.
Improvement applied or deferred: Progress corrected from 35% to 33.5%; Phase 1 returned to IN_REVIEW; release tag deferred until the matrix and review pass.
Next action and owner: LEAD_INTEGRATION records the final matrix, team supplies names/official duration, then the team rehearses to time and holds Gate 1F.
```

### Work session — 28 September 2026 (OpenRouter contingency and pacing)

```text
Participants: LEAD_INTEGRATION with Codex implementation support
Planned outcome: Add an auditable alternate LLM provider without weakening the deterministic safety boundary or mislabeling evidence.
Work completed: Added selectable Gemini/OpenRouter/deterministic provider controls; persisted the selected provider and model before queueing; added OpenRouter strict-JSON client, semantic preflight, provider-specific matrix command, metadata labels, migration, documentation, and feedback rendering. Replaced radio choices with a required native dropdown. Added a process-wide provider pacing gate so the minimum interval remains in effect when a following run creates a fresh client. Added architecture/run-flow diagrams and a seven-slide presentation outline.
Acceptance checks run: Applied runs.0004 migration; 48 pytest tests; Ruff; Pyright; Django check; migration drift check; live browser dashboard snapshot.
Evidence/commit/artifacts: EVD-016. Local credentials were configured without reading or recording their values. Browser snapshot showed the dropdown for both journeys.
Unexpected result or blocker: OpenRouter `openrouter/free` returned a temporary Nvidia overload at a 20-second interval and one length-limited completion. Gemini quota also failed with a 15-second interval. Neither provider observation was HTTP 429, so repeated key use is not established as the cause. A fixed preflight-verified model is needed before final live evidence.
Improvement applied or deferred: Provider selection is explicit at run creation; no run can silently change provider or count deterministic fallback as live evidence; pacing now covers consecutive runs in the single worker process. A distributed limiter is deferred until multiple worker processes are introduced.
Next action and owner: Team/mentor confirms Gemini-only versus provider-neutral evidence. AI_ML selects a fixed model and preflights it; LEAD_INTEGRATION runs the provider-pure 3+5 matrix and records it.
```

The default eight-minute rehearsal is specified in `docs/DEMONSTRATION_RUNBOOK.md`. Adjust timestamps only after OPEN-001 is resolved; do not silently claim an official duration.

### Work session — 28 September 2026 (fixture clarity and run-list UX)

```text
Participants: LEAD_INTEGRATION with Codex implementation support
Planned outcome: Make the accessible and blocked journeys easy to distinguish and make recent runs easier to inspect.
Work completed: Added explicit accessible-reference and intentional-barrier messages to both fixture flows; clarified the deterministic fallback action for the blocked slot control; added a friendly blocked-result explanation and human-readable issue-evidence label; added live Journey, Planner, Status, and Outcome filters to Recent evaluation runs; changed filtering to refresh only the results region without jumping the page.
Acceptance checks run: 14 fixture, manifest, and run-view tests; Django system check; fixture journeys reseeded successfully.
Evidence/commit/artifacts: Working tree changes; commit identifier to be inserted after commit.
Unexpected result or blocker: Provider reliability remains external and unchanged; no API key values were read or recorded.
Feedback received: The filter refresh was initially perceived as a page jump, so full navigation was replaced with an in-page results refresh.
Improvement applied or deferred: Accessible and blocked outcomes now have clear visual and textual contrast. Broader accessibility profiles and public targets remain deferred.
Next action and owner: LEAD_INTEGRATION records the final provider-pure matrix and commits the demonstrated revision after review.
```

### Template for future sessions

Copy this block after each session:

```text
Date/time:
Participants:
Planned outcome:
Work completed:
Acceptance checks run:
Evidence/commit/artifacts:
Unexpected result or blocker:
Feedback received:
Improvement applied or deferred:
Next action and owner:
```

---

## 13. Change log

| Version | Date | Summary |
|---|---|---|
| 1.11 | 28 September 2026 | Clarified accessible versus blocked fixture behavior, improved blocked-result wording, added live run filters, and changed filter refresh to preserve page position |
| 1.10 | 28 September 2026 | Added a required provider dropdown, cross-run process-wide pacing, architecture/run-flow diagrams, presentation outline, live OpenRouter diagnosis, and consolidated teammate handoff; 48 tests pass while the final provider-pure live matrix remains pending |
| 1.9 | 28 September 2026 | Added explicit Gemini/OpenRouter/deterministic provider selection, persisted provider/model metadata, OpenRouter structured-output preflight and provider-specific matrix support; superseded by version 1.10 live-configuration and pacing update |
| 1.8 | 28 September 2026 | Corrected progress to 33.5% and Phase 1 to IN_REVIEW; recorded Gemini 3.1 diagnostics, final individual Gemini-only proofs, strict-matrix limitations, planner/executor fixes, clean rebuilt-stack 40-test verification, headed-browser validation, and the exact demo runbook |
| 1.7 | 27 September 2026 | Completed bounded Gemini integration, provider/model preflight, typed-action safety tests, 3+5 live evidence matrix, clean Docker rebuild, UI/gallery rehearsal, and evidence-backed 35% technical milestone |
| 1.6 | 27 September 2026 | Refined navigation and run explanations; added in-page screenshot gallery with arrow-key navigation and explicit red issue-evidence highlighting |
| 1.5 | 26 September 2026 | Hardened Docker runtime to non-root, added shared artifact volume, verified fresh accessible and blocked live runs, and recorded EVD-004/EVD-005 plus DEF-005 |
| 1.4 | 26 September 2026 | Recorded the verified deterministic vertical slice, live run evidence, quality gates, infrastructure fixes, and remaining Gemini/repetition work |
| 1.3 | 26 September 2026 | Added binding role IDs, version-pin decisions, clean-setup continuity requirement, and course-requirements register with explicit institutional evidence states |
| 1.2 | 25 September 2026 | Recorded the reviewed public-target selection and changed its status to optional supporting evidence so external availability cannot block the controlled demonstration |
| 1.1 | 25 September 2026 | Replaced the day-based sprint board with development phases 1A–1F and phase-specific objectives, deliverables, and review gates |
| 1.0 | 25 September 2026 | Created initial evidence-weighted status, Phase 1 execution board, test/evidence registry, feedback process, blockers, review template, and readiness checklist |
