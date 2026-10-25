# AccessPath AI — Master Project Plan and Context

**Document role:** Canonical source of truth for the project  
**Version:** 2.3  
**Date:** 26 September 2026  
**Course:** 5-credit B.Tech CSE project  
**Institution:** BML Munjal University  
**Team size:** 3 members  
**Project status:** Planning and specification  
**Next action:** Complete Phase 0 and approve this document before implementation

---

## 1. How to use this document

This document contains the agreed project direction, scope, terminology, requirements, architecture, recommended technology stack, security model, evaluation method, delivery phases, and material that can be reused in presentations and reports.

It should be used by the whole team as the primary reference for:

- deciding whether a feature belongs in the current project;
- planning and assigning implementation work;
- reviewing architecture and technical decisions;
- designing the database and API;
- creating the project presentation, synopsis, proposal, and final report;
- defining the evaluation methodology;
- explaining the project to mentors, evaluators, and future contributors; and
- preventing the scope and terminology from changing informally.

When the project direction changes, update this document first. Every material change should update the version and change log.

### Document authority

The following order applies when information conflicts:

1. The latest explicitly approved decision recorded in this document.
2. A later Architecture Decision Record created during implementation.
3. The implementation and its automated tests.
4. Presentation slides, reports, chats, and older drafts.

This plan intentionally replaces all earlier project-context and review documents.

---

## 2. Executive summary

AccessPath AI is a web-based developer platform for evaluating whether complete digital journeys are accessible to people with disabilities. Its first implementation track evaluates whether a defined website task can be completed using keyboard-only interaction by a person with a motor disability. A developer provides an approved website or test environment, a plain-language task goal, and controlled test data. The system opens the target in an isolated browser, attempts the journey using only permitted keyboard actions, records evidence at every step, and reports whether the task completed, was blocked by a reproducible keyboard barrier, or remained inconclusive.

Keyboard accessibility is the **current implementation focus**, not the permanent product boundary. The complete product vision includes visual and screen-reader accessibility, hearing and multimedia accessibility, cognitive accessibility, mobile accessibility, document accessibility, and additional input modalities. Those profiles will be added in later phases on the same journey, evidence, rules, reporting, and compliance architecture.

Complete functional journeys remain part of the project. Account creation, authentication, booking, checkout and payment, forms, applications, messaging, uploads, consent, recovery, and other state-changing workflows must be testable through safe execution modes. During development they will run in owner-controlled fixtures, staging systems, provider sandboxes, mail sinks, payment test modes, or reversible test accounts. The public-target mode will remain non-destructive unless the target owner explicitly configures and authorizes a controlled test environment.

The system will support compliance evaluation and traceability across relevant standards, but no automated tool can truthfully certify every accessibility requirement by itself. AccessPath AI will therefore identify which requirements are evaluated automatically, which are semi-automated, which require manual or assistive-technology review, and which are planned for a later profile. It will not convert incomplete automated coverage into a whole-product legal certification.

The central technical principle is:

> AI may plan the next keyboard action, but deterministic browser observations, versioned evaluation rules, and recorded evidence decide what occurred.

The system will be production-shaped rather than local-only. The web API, durable job queue, browser workers, database, and object storage will be separate logical components so long-running browser tests survive restarts and can scale independently. The initial deployment can remain small and economical, but it must use the same boundaries expected in a larger deployment.

---

## 3. Project vision

### Vision statement

Make complete user-journey accessibility testing understandable and practical for development teams by showing where a person using a declared accessibility profile can or cannot complete an important task.

### Mission

Create an open, evidence-driven evaluation platform that combines constrained automation, versioned accessibility rules, assistive-technology-aware profiles, bounded AI planning, and human review to identify task-level barriers that ordinary page scans can miss or cannot prioritize.

### Product evolution

The product is designed from the beginning for multiple accessibility profiles and complete functional journeys. Delivery is deliberately sequential:

1. keyboard-only motor-accessibility journeys;
2. authenticated and state-changing keyboard journeys in controlled environments;
3. broader browsers and CI/regression workflows;
4. visual and screen-reader profiles using real accessibility APIs and assistive technologies;
5. hearing/multimedia and cognitive-accessibility profiles;
6. mobile, document, and native-application profiles; and
7. selectable regulatory and procurement reporting profiles.

Later profiles are committed project roadmap items, not features claimed by the initial release.

---

## 4. Problem statement

Most automated accessibility tools identify rule violations in a rendered page or component. This is useful, but it does not by itself establish whether a keyboard-only user can complete a multi-step task such as selecting an appointment, completing a form, or reaching a review page.

Developers often face three practical problems:

1. They receive a long list of findings without knowing which ones block an important user journey.
2. Some behavioral barriers require interaction and state changes rather than a single page scan.
3. Writing and maintaining scripted keyboard tests requires both automation skill and accessibility expertise.

Examples of task-level barriers include:

- a required control that never receives sequential keyboard focus;
- a custom control that receives focus but does not respond to its expected key;
- a dialog from which focus cannot escape after the user finishes or cancels;
- focus disappearing or returning to an illogical place after a route or component change;
- a keyboard user being unable to reach or recover from a validation error; and
- a component whose declared interaction pattern does not match its implemented keys.

AccessPath AI addresses this gap by attempting a declared task with a selected accessibility profile and producing step-level evidence about the journey. The keyboard profile is implemented first; later profiles reuse the same journey and evidence foundation.

---

## 5. Goals and measurable objectives

### 5.1 Project goals

**G1 — Evaluate real task completion**  
Determine whether a declared web task can be completed using the supported keyboard profile.

**G2 — Detect and localize keyboard barriers**  
Identify the step, component, action, and state transition associated with a reproducible barrier.

**G3 — Produce trustworthy evidence**  
Record enough structured evidence for a developer or evaluator to reproduce and review every finding.

**G4 — Compare journey testing with automated scanning**  
Measure which verified barriers are detected by the journey evaluator, by per-state axe-core scans, by both, or by neither.

**G5 — Build a deployable foundation**  
Create a cloud-deployable system with durable jobs, isolated workers, persistent metadata, object storage, security controls, and observable execution.

**G6 — Demonstrate academic rigor**  
Evaluate the system against a controlled benchmark and authorized real-world journeys using independently reviewed ground truth.

**G7 — Cover complete functional journeys**  
Evaluate accessibility across authentication, account creation, booking, checkout and payment, forms, messaging, uploads, consent, recovery, and other end-to-end workflows in appropriately controlled environments.

**G8 — Build comprehensive compliance traceability**  
Maintain a versioned register mapping product rules and review procedures to relevant accessibility standards, regulatory profiles, evidence, implementation status, and coverage method.

**G9 — Expand accessibility profiles without redesigning the platform**  
Use a shared journey, rule, evidence, report, and evaluation architecture that can later support screen readers, visual checks, multimedia, cognitive review, mobile, documents, native applications, and other input methods.

### 5.2 Measurable objectives

The team will:

1. Implement a deterministic keyboard testing kernel before adding AI navigation.
2. Support at least four verified barrier types for the first major demonstration.
3. Expand to the declared MVP detector catalogue before final evaluation.
4. Store an immutable step history and evidence bundle for every completed run.
5. Ensure API or worker restarts do not silently lose accepted runs.
6. Prevent the planner from performing any operation outside the allowed keyboard-action schema.
7. Evaluate controlled fixtures with accessible and deliberately broken variants.
8. Compare results with manual keyboard evaluation and axe-core at matched page states.
9. Report precision, recall, false completion, false blocking, inconclusive rate, reproducibility, latency, and estimated model cost.
10. Deploy a working staging system accessible to the project team and evaluators.
11. Demonstrate keyboard accessibility across controlled examples of account creation, authentication, booking, checkout/payment sandbox, messaging, upload, and recovery workflows before declaring the keyboard track complete.
12. Maintain a compliance coverage register with `automated`, `semi_automated`, `manual`, `planned`, and `not_applicable` states.
13. Add later accessibility profiles through explicit roadmap phases and profile-specific validation rather than informal feature additions.

### 5.3 Initial quality targets

These are target thresholds, not guaranteed results. They must be reviewed after the pilot benchmark.

| Measure | Initial target |
|---|---:|
| Precision on supported barrier events | At least 0.80 |
| Recall on supported barrier events | At least 0.70 |
| False-completion rate | No more than 0.05 |
| Repeated-run outcome agreement | At least 0.90 |
| Accepted jobs lost during API restart test | 0 |
| Cross-user artifact access failures | 100% correctly denied |
| Findings with reproducible evidence | 100% |
| Findings presented as whole-site certification | 0 |

Targets may be revised only with a recorded reason and without hiding unfavorable results.

---

## 6. Target users and value

### Primary user

A developer or QA engineer who owns or is authorized to test a website and wants to understand whether an important flow is keyboard operable.

### Secondary users

- accessibility specialists reviewing evidence;
- engineering leads prioritizing remediation;
- students and researchers studying agent-based accessibility testing; and
- product teams validating a fix by rerunning the same journey.

### Value delivered

- A journey result tied to a concrete task rather than an abstract score.
- Evidence showing where progress stopped.
- A distinction between verified blockers and observations needing review.
- A comparison with conventional automated scanning.
- Reproduction steps and standards references.
- A rerun that shows whether behavior changed after a fix.

### Primary user story

> As a developer responsible for an authorized website, I want to provide a task goal and have the system attempt it using only keyboard interactions so that I can see whether the task is completable, where a keyboard barrier occurs, and what evidence I should review or fix.

---

## 7. Project scope and phased focus

### 7.1 Full project scope

AccessPath AI is intended to cover complete accessibility evaluation workflows across relevant disabilities, technologies, standards, and end-to-end product journeys. The full project scope includes:

- public and authenticated web applications;
- account registration, sign-in, sign-out, password recovery, and multi-step authentication;
- booking, reservation, appointment, and cancellation journeys;
- product discovery, cart, checkout, payment, confirmation, refund, and order-history journeys;
- forms, applications, validation, review, submission, and correction;
- composing, sending, receiving, and managing messages or notifications;
- uploads, downloads, consent, preferences, and account management;
- desktop and later mobile web journeys;
- later native mobile, document/PDF, and native desktop evaluation;
- motor, visual, hearing, cognitive, and multi-disability accessibility profiles;
- automated, semi-automated, manual, and assistive-technology evaluation methods;
- compliance traceability and reporting across relevant global and regional standards;
- regression testing, reruns, CI integration, and scheduled monitoring; and
- developer, accessibility-specialist, reviewer, and team workflows.

The project will be delivered in phases. A feature can be in the full project scope without being implemented in the first release.

### 7.2 Current implementation focus: keyboard motor accessibility

The first implementation track focuses on people with motor disabilities who navigate and operate the web through a keyboard or keyboard-compatible input. It includes:

- desktop web applications;
- Chromium as the first browser;
- websites and test environments explicitly approved for evaluation;
- public, authenticated, and state-changing journeys when a safe controlled environment is available;
- a declared start URL and plain-language task goal;
- synthetic test identities, form data, and sandbox credentials;
- keyboard-only actions:
  - `Tab`;
  - `Shift+Tab`;
  - `Enter`;
  - `Space`;
  - arrow keys;
  - `Escape`; and
  - text entry into the currently focused editable control;
- goal-driven navigation with a bounded AI planner;
- deterministic browser observation and state comparison;
- a declared catalogue of keyboard barrier checks;
- axe-core scans at meaningful browser states;
- screenshots, traces, focus history, and structured evidence;
- completed, blocked, inconclusive, environment-blocked, and safety-stopped outcomes;
- rerun and regression comparison;
- a controlled benchmark plus authorized real-world evaluation; and
- cloud deployment with durable execution.

### 7.3 Complete journeys in the keyboard track

The keyboard track must not be limited to simple navigation. It should progressively cover:

| Journey family | Safe implementation approach |
|---|---|
| Account creation | Synthetic users in a fixture or owner-controlled staging environment; email verification through a mail sink |
| Authentication | Test accounts and secrets supplied through an encrypted secret reference, never placed in prompts or logs |
| Password recovery | Test inbox/mail sink and disposable user records |
| Booking or appointment | Staging inventory or test slots with automated cleanup/cancellation |
| Checkout and payment | Payment-provider test mode, fake products, and sandbox cards; never a real charge |
| Forms and applications | Synthetic records and a reversible test backend |
| Messaging | Mail/chat sink or test recipient controlled by the target owner |
| File upload | Generated non-sensitive fixtures, malware-safe size/type limits, and automatic cleanup |
| Consent and preferences | Test accounts and resettable state |
| Destructive actions | Dedicated fixtures or disposable records with an explicit approval and cleanup policy |

At least one authenticated journey and representative state-changing sandbox journeys should be part of the completed keyboard-accessibility track. Public production targets remain restricted to actions that cannot cause harm.

### 7.4 Later accessibility profiles

These are deferred implementation tracks, not excluded project areas:

- screen-reader and accessibility-tree behavior using declared AT/browser combinations;
- visual accessibility, including contrast, zoom/reflow, text spacing, focus appearance, and non-text content;
- hearing and multimedia accessibility, including captions, transcripts, audio description, and media controls;
- cognitive and learning accessibility, including predictable interaction, clear instructions, error prevention, time limits, and cognitive load;
- speech input, switch access, voice control, pointer alternatives, touch, and other motor-input profiles;
- mobile web and native mobile accessibility;
- PDF and document accessibility;
- native desktop software accessibility;
- cross-browser and cross-platform evaluation; and
- organization-level dashboards, CI/CD enforcement, team review, and procurement/compliance profiles.

Each profile must have its own supported rules, environment matrix, evidence model, benchmark, limitations, and qualified claims before it is presented as implemented.

### 7.5 Permanent safety and integrity boundaries

The following are prohibited or intentionally never claimed:

- testing a target without ownership or explicit authorization;
- bypassing authentication, CAPTCHA, bot protection, rate limits, or site policy;
- making real payments or causing unapproved financial, legal, medical, communication, or account effects;
- using real personal, identity, health, education, or payment data when synthetic data can be used;
- automatically changing a target website without an explicit remediation workflow and human approval;
- automatically merging model-generated fixes;
- presenting partial automated coverage as complete WCAG or legal certification; and
- hiding unsupported, inconclusive, negative, or failed results.

### 7.6 Important interpretation rule

Accessible names, labels, roles, and states may be collected during the keyboard phase because they help identify and interpret controls. They become screen-reader evidence only when a later assistive-technology profile tests them through declared accessibility APIs and AT/browser combinations.

Visible focus is part of keyboard accessibility and may be evaluated in the current track when a reliable rule exists. Ambiguous visual-quality judgments must be marked `needs_review` until the visual profile provides stronger validation.

### 7.7 Functional journey catalogue

The target is accessibility across complete processes, not isolated pages. Controlled fixtures and later authorized target environments should represent these journey families:

| Journey | Representative checkpoints | Keyboard-focused questions now | Later profile additions |
|---|---|---|---|
| Registration/onboarding | Start, personal data, verification, terms, preferences, completion | Can every field/control be reached and operated; are errors recoverable; can the user review and submit? | Screen-reader announcements, visual instructions, cognitive clarity, mobile input |
| Authentication | Sign-in, show/hide password, MFA, recovery, session timeout, sign-out | Are all methods keyboard operable; is focus managed after errors/routes; can timeout be extended? | Accessible authentication, AT labels/status, cognitive burden, mobile biometrics |
| Booking/reservation | Search, filters, date/time picker, details, review, confirm, cancel | Can composite widgets be operated; can selection and confirmation occur without pointer input? | Calendar announcements, visual state, time pressure, mobile gesture alternatives |
| Commerce/payment | Search, product options, cart, address, delivery, payment test mode, review, confirmation/refund | Are product controls, quantity, address, payment iframe, validation, and review operable? | Price/status announcements, zoom/reflow, cognitive error prevention, mobile wallets |
| Multi-step form/application | Instructions, inputs, conditional steps, validation, save/resume, review, submit, correction | Is the step order logical; are errors reachable; is data retained; can the user correct and continue? | Labels/descriptions, reading order, language, error announcements, cognitive support |
| Messaging/communication | Recipient, subject, editor, attachments, review, send, reply, delete | Can rich editors, recipient pickers, attachments, dialogs, and send controls be used by keyboard? | AT editor behavior, visual formatting, caption/transcript support, cognitive clarity |
| Upload/download | File chooser, validation, progress, cancel, preview, remove, download | Are chooser, progress, cancellation, and removal available without drag/drop? | Status announcements, contrast, file metadata, document accessibility |
| Consent/preferences | Notice, choices, granular settings, save, withdraw/reset | Can choices be reached without coercive focus behavior; can consent be changed or withdrawn? | Plain language, visual hierarchy, AT semantics, cognitive accessibility |
| Account/profile management | View/edit data, security settings, notifications, export, deletion | Are controls, confirmation dialogs, reauthentication, and recovery paths operable? | Screen-reader state, visual warnings, cognitive error prevention, mobile/native patterns |
| Help/support | Search help, FAQ, chatbot/contact form, ticket creation, status | Can help be found and used at the point of failure without losing journey state? | Reading level, AT announcements, multimedia alternatives, consistent help criteria |

The catalogue is extensible. A new journey family must declare its side effects, test environment, cleanup, accessibility profiles, compliance mappings, completion signals, and benchmark cases.

---

## 8. Canonical terminology

The team should use these terms consistently in code, UI, presentations, database naming, and reports.

### Evaluation scope

**Accessibility Profile:**  
A declared combination of disability-related needs, input/output methods, assistive technology, browser/platform, and evaluation rules.  
_Avoid:_ disability mode, universal scan.

**Test Target:**  
The website or web-application origin that the evaluator is authorized to assess.  
_Avoid:_ scrape target, victim site.

**Test Environment:**  
An owner-authorized target configuration containing the origins, accounts, sandbox integrations, data policy, cleanup behavior, and side-effect permissions for a journey.  
_Avoid:_ URL only, production credentials.

**Execution Mode:**  
The safety policy governing which journey effects are allowed: observe-only, sandbox-transactional, or explicitly approved production audit.  
_Avoid:_ unrestricted mode.

**Journey Specification:**  
The declared accessibility profile, test environment, start point, task goal, allowed target scope, controlled inputs, completion signals, and cleanup expectations for one evaluation.  
_Avoid:_ prompt, generic test case.

**Task Goal:**  
A concrete user outcome expressed independently of the steps used to reach it.  
_Avoid:_ command, instruction.

**Keyboard Profile:**  
The documented set of keyboard inputs and interaction conventions available during an evaluation.  
_Avoid:_ disabled mode, keyboard simulation mode.

**Supported Finding:**  
A barrier category for which the product declares a repeatable evaluation method and outcome semantics.  
_Avoid:_ everything the agent notices.

### Journey execution

**Test Run:**  
One immutable execution of a journey specification in a recorded browser and evaluator environment.  
_Avoid:_ mutable session.

**Journey:**  
The ordered sequence of observations and keyboard actions taken while attempting a task goal.  
_Avoid:_ crawl, arbitrary script.

**Step:**  
One observed browser state together with the proposed action, executed action, and resulting state.  
_Avoid:_ LLM turn.

**Observation:**  
Recorded facts about a browser state, such as the URL, focused element, relevant structure, and visible content.  
_Avoid:_ reasoning.

**Action:**  
One keyboard operation permitted by the keyboard profile.  
_Avoid:_ tool call, click.

**Completion Signal:**  
An observable condition indicating that the task goal has been reached.  
_Avoid:_ agent belief.

### Results and evidence

**Journey Outcome:**  
The result of attempting a task: `completed`, `blocked`, or `inconclusive` in the recorded environment.  
_Avoid:_ website passed, compliance result.

**Journey Blocker:**  
A reproducible barrier that prevents progress toward the task goal under the keyboard profile.  
_Avoid:_ generic bug, automatic WCAG violation.

**Finding:**  
A normalized accessibility observation supported by evidence and assigned a review state.  
_Avoid:_ failure count.

**Rule Evaluation:**  
The outcome of one declared evaluation rule: `passed`, `failed`, `cantTell`, or `inapplicable`.  
_Avoid:_ scan result.

**Evidence:**  
Recorded material needed to reproduce or review a finding, such as focus history, state changes, screenshots, traces, and sanitized element context.  
_Avoid:_ screenshot alone.

**Needs Review:**  
A finding for which the available evidence is insufficient to assert a pass or failure automatically.  
_Avoid:_ low-confidence failure.

**Inconclusive:**  
A journey outcome used when completion or a verified blocker cannot be established because of ambiguity, limits, or target/tool behavior.  
_Avoid:_ timeout failure.

**Baseline Observation:**  
A result from a declared comparator, such as axe-core, at a specific browser state.  
_Avoid:_ ground truth.

**Ground Truth:**  
The independently reviewed reference label used to evaluate the system, including documented disagreement resolution.  
_Avoid:_ one team member's manual result.

**Rerun:**  
A new test run linked to an earlier run for comparison after a change.  
_Avoid:_ updated or overwritten run.

---

## 9. Product behavior

### 9.1 Inputs

Every run requires:

- an authenticated project user;
- a selected accessibility profile, initially `keyboard_motor_desktop`;
- an approved test environment and HTTPS start URL;
- a task goal;
- the allowed target origin or origins;
- confirmation that the user is authorized to test the target;
- controlled input values if the task contains forms;
- an execution mode;
- explicit completion signals; and
- cleanup expectations for state-changing sandbox journeys.

Optional inputs include:

- expected URL or URL pattern;
- expected text or element state;
- encrypted references to disposable test credentials;
- sandbox integration references such as a payment test account or mail sink;
- allowed state-changing checkpoints;
- expected side effects and rollback verification;
- maximum actions;
- maximum duration;
- viewport and locale; and
- additional allowed same-owner origins.

Secrets are resolved inside the isolated worker only when required. They are not returned to the planner, included in screenshots when avoidable, stored in event logs, or persisted in report content.

#### Completion signal contract (`completion_policy.v1`) — resolves MS-001

Every journey must store one immutable, versioned completion policy. The current implementation supports only deterministic signals; arbitrary JavaScript, XPath, model judgment, and free-form selectors are not completion signals.

```json
{
  "schema_version": "completion_policy.v1",
  "mode": "all",
  "signals": [
    {
      "id": "confirmation_url",
      "type": "url_path_equals",
      "expected": "/accessible/confirmation/"
    },
    {
      "id": "confirmation_status",
      "type": "element_text_equals",
      "locator": {"by": "test_id", "value": "booking-status"},
      "expected": "Appointment confirmed",
      "case_sensitive": true
    },
    {
      "id": "confirmation_state",
      "type": "element_attribute_equals",
      "locator": {"by": "test_id", "value": "booking-status"},
      "attribute": "data-booking-state",
      "expected": "confirmed"
    }
  ],
  "stability": {"consecutive_observations": 2, "interval_ms": 500}
}
```

`CompletionPolicyV1` fields are fixed as follows:

- `schema_version`: literal `completion_policy.v1`.
- `mode`: literal `all` for the current implementation; every signal must match.
- `signals`: one to five uniquely identified `CompletionSignalV1` records.
- `type`: one of `url_path_equals`, `element_present`, `element_text_equals`, or `element_attribute_equals`.
- `locator`: required for element signals and limited to `{by: "test_id", value: <non-empty string>}` in controlled fixtures. Public-target locators may later add reviewed `role_and_name` support under a new schema version.
- `expected`: required except for `element_present`; string comparison is exact after Unicode normalization and surrounding-whitespace trim unless `case_sensitive` is explicitly `false`.
- `attribute`: required only for `element_attribute_equals`; script/event attributes are forbidden.
- `stability`: the complete policy must match in two consecutive observations separated by 500 ms after the last executed action.

The journey is `completed` only when the entire policy matches. A model statement is never a completion signal and cannot override a failed or missing signal. An invalid policy is rejected before run creation. If execution ends without a stable match and without a verified supported blocker, the outcome is `inconclusive`, not `completed` or `blocked`.

### 9.2 Outputs

Every terminal run produces:

- run state and journey outcome;
- tested target and task goal;
- accessibility profile and execution mode;
- environment and version metadata;
- ordered journey timeline;
- actions attempted and their observable effects;
- verified findings;
- observations needing review;
- axe-core baseline observations by state;
- screenshots and traces permitted by the retention policy;
- reproducibility instructions;
- standards references;
- limitations and unsupported areas; and
- observed side effects and cleanup status for controlled transactional journeys; and
- a link to create a rerun.

### 9.3 Result language

The user interface and reports must use precise language:

- **Task completed:** the declared completion signal was observed in the recorded environment.
- **Task blocked:** a supported, reproducible barrier prevented further progress.
- **Inconclusive:** the system could not verify completion or a supported blocker.
- **Environment blocked:** target access, bot defense, navigation, or browser environment prevented evaluation.
- **Safety stopped:** the next step could cause an unapproved real-world side effect.
- **Cleanup failed:** the controlled journey completed or stopped, but expected test-data cleanup could not be verified and requires operator attention.

The product must never translate “task completed” into “website is accessible” or “WCAG compliant.”

---

## 10. End-to-end user flow

### 10.1 Create a run

1. The user signs in.
2. The user selects an accessibility profile and approved test environment.
3. The user enters the start URL and task goal.
4. The user supplies controlled data, completion signals, and any sandbox credential references.
5. The user selects an execution mode and reviews the allowed side effects and cleanup plan.
6. The application shows the test policy, scope, and environment restrictions.
7. The user confirms authorization to test the target and, when applicable, to perform the declared sandbox actions.
8. The API validates the input, target, credential references, and action policy.
9. The API creates a durable run and returns a run identifier.

### 10.2 Observe progress

1. The progress page subscribes to server-sent events.
2. The user sees queued, starting, observing, acting, evaluating, and finalizing states.
3. The interface shows concise audit facts, not hidden model chain-of-thought.
4. The user may request cancellation.
5. For controlled state-changing journeys, the progress view also shows the current checkpoint and cleanup state without exposing secrets.

### 10.3 Review the result

1. The report begins with the task outcome and scope.
2. A timeline shows each state and permitted keyboard action.
3. Findings show evidence, reproduction steps, rule outcome, and review status.
4. Baseline observations are kept separate from journey findings.
5. The report states what was not tested.
6. The report records expected/observed side effects and cleanup status when applicable.
7. The user can create a rerun after making a change.

### 10.4 Compare a rerun

1. A rerun copies the earlier journey specification into a new immutable run.
2. The system executes it under a newly recorded environment.
3. The comparison classifies findings as resolved, persistent, new, or incomparable.
4. The original report remains unchanged.

---

## 11. System execution flow

```text
1. User submits Journey Specification and approved Test Environment
                |
                v
2. Django application authenticates user and validates target/action/side-effect policy
                |
                v
3. One database transaction stores Test Run plus an outbox job record
                |
                v
4. Outbox dispatcher publishes idempotently to Celery; worker claims the job
                |
                v
5. Worker resolves permitted sandbox secrets and starts an isolated browser
                |
                v
6. Observer captures initial state and baseline scan
                |
                v
7. Planner proposes one allowed keyboard action
                |
                v
8. Policy validator accepts or rejects proposed action
                |
                v
9. Executor sends real keyboard input
                |
                v
10. State differ records observable before/after changes
                |
                v
11. Rule evaluators produce passed/failed/cantTell/inapplicable
                |
                v
12. Goal oracle checks declared completion signals
                |
       +--------+---------+
       |                  |
   continue          terminal outcome
       |                  |
       +------ loop ------+
                          |
                          v
13. Worker verifies or performs declared sandbox cleanup
                          |
                          v
14. Reporter finalizes evidence, findings, side effects, and limitations
                          |
                          v
15. Metadata persists in PostgreSQL; artifacts in object storage
                          |
                          v
16. UI receives progress/final result through SSE or polling
```

---

## 12. Keyboard evaluation engine

### 12.1 Component responsibilities

**Observer**

- Captures current URL and origin.
- Identifies the active element.
- Records a stable element fingerprint and locator bundle.
- Captures relevant DOM and accessibility semantics.
- Records visible text and status changes.
- Detects dialogs, overlays, and route changes.
- Produces screenshots and trace references.
- Creates a compact state fingerprint.

**Planner**

- Receives the task goal, permitted synthetic data, action history, and bounded page observation.
- Proposes exactly one action from the typed action schema.
- Has no browser, shell, network, database, or storage tool access.
- Does not determine compliance or final findings.

**Planner observation bound (`planner_observation.v1`)**

- Include the active element first, then at most 40 visible or sequentially reachable interactive elements in deterministic tab-order/DOM-order tie-break order.
- Limit each element's sanitized accessible name to 120 characters and visible-text summary to 4,000 characters total.
- Include at most three active dialog/overlay summaries and the last eight normalized action/effect records.
- Emit `elements_truncated`, `visible_text_truncated`, and `history_truncated` booleans whenever a limit applies; the planner must use keyboard exploration rather than request more page data.
- Never include raw HTML, scripts, hidden form values, passwords, tokens, or unredacted free-text form input.

**Policy Validator**

- Confirms the action is part of the keyboard profile.
- Confirms typing is directed to an editable focused control.
- Applies action, duration, origin, and safety budgets.
- Stops actions that could create an unapproved side effect.
- Rejects malformed or semantically invalid model output.

For a `type` proposal whose focused target is not an enabled editable control, the validator returns `rejected / TYPE_TARGET_NOT_EDITABLE`, performs no browser action, and supplies only that code to the next planner turn. One replan is allowed. A second rejection with the same code terminates the run as `agent_error`; it is never reclassified as a keyboard barrier or `inconclusive`.

**Executor**

- Sends the real keyboard event to the browser.
- Never invokes a control with mouse input.
- Never executes page JavaScript to bypass an interaction barrier.

**State Differ**

- Compares URL, focus, DOM, visible content, overlays, and relevant network outcomes.
- Distinguishes meaningful progress from animation, timestamps, and unrelated page noise.
- Supplies deterministic evidence to detectors and the goal oracle.

`meaningful_progress` is a deterministic boolean. It is `true` only when at least one of these changes after an approved action: normalized URL path/query/fragment; active-element fingerprint; a task-relevant control's value, checked, selected, disabled, `aria-expanded`, `aria-invalid`, or `aria-current` state; active dialog/overlay identity; declared task checkpoint; or sanitized `status`/`alert` content. Clock, date, random-ID, animation-frame, analytics, and unrelated visible-text changes are excluded. The model does not set this field.

**Rule Evaluators**

- Apply versioned rules with declared applicability, assumptions, expectations, and outcomes.
- Never convert uncertainty into a failure.
- Link failures to captured evidence.

**Goal Oracle**

- Uses explicit completion signals where available.
- May use model interpretation only as supporting evidence.
- Produces `inconclusive` if completion is ambiguous.

For `completion_policy.v1`, deterministic signals are the sole decision authority. A planner may record a non-decisive `completion_hypothesis` for debugging, but the oracle neither queries the model for confirmation nor uses that hypothesis to pass a failed/missing signal. A stable policy match yields `completed`; otherwise the oracle continues or returns `inconclusive` when the run ends without a verified blocker.

**Reporter**

- Normalizes findings.
- Separates journey findings from baseline scan observations.
- Maps supported findings to applicable standards references.
- Adds limitations, environment metadata, and reproduction steps.

### 12.2 Allowed action schema

Conceptually, a proposed action contains:

```json
{
  "action": "tab | shift_tab | enter | space | arrow_up | arrow_down | arrow_left | arrow_right | escape | type",
  "value": "only present for type",
  "target_hint": "short audit label for the currently focused element",
  "purpose": "short application-facing rationale"
}
```

The exact schema will be versioned. Provider-native structured output must be used, followed by server-side semantic validation.

### 12.3 State fingerprint

A state fingerprint should use stable, privacy-minimized observations such as:

- normalized URL;
- active-element fingerprint;
- relevant component and dialog state;
- digest of relevant visible text;
- digest of a sanitized DOM/accessibility snapshot;
- screenshot perceptual hash where appropriate; and
- declared task checkpoint.

Loop detection should operate on repeated state/action sequences. A repeated key or repeated element alone is not enough to prove a trap.

`LOOP_REPEAT_THRESHOLD` is fixed at `3` for the initial keyboard profile. A loop candidate exists only when the same `(state_fingerprint_before, normalized_action)` pair occurs three times in one run, each occurrence has `meaningful_progress=false`, and each `state_fingerprint_after` equals its corresponding `state_fingerprint_before`. The terminal result is `inconclusive / LOOP_BUDGET_EXHAUSTED` unless KBD-003 independently verifies a keyboard trap through forward, backward, and standard-exit evidence. Changing this threshold requires a rule/profile version change and benchmark rerun.

---

## 13. Supported detector catalogue

### 13.1 Required for the first major demonstration

| ID | Finding | Required evidence | Important exception |
|---|---|---|---|
| KBD-001 | Required task control unreachable by sequential keyboard navigation | Candidate inventory, tab sequence, task relevance, repeated traversal | A non-interactive visual element is not a control |
| KBD-002 | Focused control not operable by its expected keyboard action | Control pattern, expected key, before/after state, bounded retries | Lack of change may be correct if a prerequisite is missing |
| KBD-003 | True keyboard trap | Entry context, focus cycle, forward/backward tests, standard exit attempts | Intentional focus containment in an open modal is valid if the user can close it |
| KBD-004 | Focus lost or restored to an illogical location | Before/after focus target, removed node, route/dialog event, expected restoration | Focusing the document may be intentional in a declared pattern |

### 13.2 Full MVP catalogue

| ID | Finding | Automatic outcome policy |
|---|---|---|
| KBD-001 | Required task control unreachable | Fail only with reproducible candidate and traversal evidence |
| KBD-002 | Expected keyboard activation does not work | Fail only for a recognized native/APG interaction with satisfied preconditions |
| KBD-003 | Keyboard trap | Fail only when standard exit behavior and task recovery are unavailable |
| KBD-004 | Focus loss or incorrect restoration | Fail only when task context is demonstrably lost |
| KBD-005 | Declared composite widget key model is not implemented | Evaluate only recognized supported patterns |
| KBD-006 | Focused control is entirely obscured | Fail only with reliable geometry/overlay evidence; otherwise needs review |
| KBD-007 | Unexpected context change on focus or selection | Fail only when the change matches declared rule applicability |
| KBD-008 | Keyboard user cannot reach or recover from a validation error | Fail with error state, focus path, and blocked progress evidence |
| KBD-009 | Harmful focus order | Default to needs review unless a deterministic contradiction changes meaning or operation |
| KBD-010 | Task requires unsupported drag, hover, or pointer-only behavior | Fail only when no keyboard-equivalent path exists for required functionality |

### 13.3 Diagnostic observations

The following may be displayed separately during the keyboard phase. They also become inputs to later visual, screen-reader, form, and cognitive-accessibility profiles:

- missing accessible name;
- missing form label or instruction;
- inconsistent role/state information;
- axe-core violations observed at a journey checkpoint; and
- elements requiring manual accessibility review.

### 13.4 Budget and environment outcomes

The following are not accessibility failures:

- maximum action count reached;
- maximum duration reached;
- target blocked automation;
- navigation or DNS failure;
- CAPTCHA encountered;
- model returned invalid actions;
- browser crashed;
- evidence storage failed; or
- the task goal lacked a verifiable completion signal.

They produce `inconclusive`, `environment_blocked`, `agent_error`, or `system_error` as appropriate.

---

## 14. Standards and compliance alignment

### 14.1 Compliance coverage model

“Covered” must not mean “an automated scanner mentioned the criterion.” Every requirement in a selected standards profile receives one coverage state:

| Coverage state | Meaning |
|---|---|
| `automated` | A versioned rule can determine an outcome from machine-observable evidence within declared limits |
| `semi_automated` | The system gathers evidence and asks a reviewer one or more structured questions |
| `manual` | A qualified human or user evaluation is required and the platform manages the protocol and evidence |
| `at_required` | Declared assistive technology and platform/browser combinations must be used |
| `planned` | The criterion belongs to the project roadmap but its evaluation profile is not implemented yet |
| `not_applicable` | The requirement does not apply to the declared target, content, or journey, with a recorded reason |
| `unsupported` | The current release cannot evaluate it and must say so explicitly |

The compliance register must record:

- standards/profile name, edition, jurisdiction, and effective date;
- criterion or clause identifier;
- applicability conditions;
- accessibility profile and supported environment;
- rule or review-protocol version;
- coverage state;
- required evidence;
- result and reviewer identity where applicable;
- known limitations; and
- implementation and validation status.

This allows AccessPath AI to manage comprehensive compliance work without falsely claiming that every criterion can be automated.

### 14.2 Canonical accessibility baseline

The canonical global web baseline is **WCAG 2.2 Level A and AA**. AAA criteria may be mapped and evaluated where a project chooses them, but blanket AAA conformance is not the default product claim.

The full WCAG principles are part of the project plan:

| Principle | Coverage areas | Delivery track |
|---|---|---|
| Perceivable | Text alternatives, time-based media, adaptable structure, sensory characteristics, contrast, text spacing, reflow, non-text contrast, content on hover/focus | Static rules plus later visual, screen-reader, multimedia, and manual profiles |
| Operable | Keyboard, traps, timing, seizures/physical reactions, navigation, focus, input modalities, dragging, target size, redundant entry, accessible authentication | Keyboard motor profile first; visual, cognitive, pointer/touch, and mobile extensions later |
| Understandable | Language, predictability, labels/instructions, errors, prevention, consistent help, cognitive assistance | Static checks plus semi-automated/manual cognitive and usability protocols |
| Robust | Parsing/compatibility, name-role-value, status messages, accessibility API exposure | Static rules initially; later real browser/accessibility API and AT profiles |

The keyboard motor profile begins with, but is not limited to:

- 2.1.1 Keyboard;
- 2.1.2 No Keyboard Trap;
- 2.1.4 Character Key Shortcuts;
- 2.2 timing criteria where time prevents task completion;
- 2.4.1 Bypass Blocks;
- 2.4.3 Focus Order;
- 2.4.7 Focus Visible;
- 2.4.11 Focus Not Obscured (Minimum);
- 2.5.1 Pointer Gestures and 2.5.7 Dragging Movements where a keyboard equivalent is needed;
- 3.2.1 On Focus and 3.2.2 On Input;
- applicable labels, errors, prevention, redundant-entry, and accessible-authentication criteria under 3.3; and
- 4.1.2 Name, Role, Value as supporting component evidence.

Use the WAI-ARIA specification and Authoring Practices Guide for expected semantics and keyboard behavior in recognized widget patterns. APG is implementation guidance and does not replace normative WCAG requirements.

### 14.3 Standards, regulatory, and procurement profiles

The product architecture must support selectable, versioned reporting profiles. Inclusion below means the project will maintain mappings and evaluation plans; it does not mean the current keyboard release already validates every clause.

| Profile or framework | Project use |
|---|---|
| WCAG 2.2 A/AA | Canonical web accessibility requirements and result mapping |
| WAI-ARIA and ARIA APG | Component semantics and expected interaction patterns |
| ACT Rules Format | Transparent automated/semi-automated rule design and outcomes |
| WCAG-EM 2.0 | Scope, representative sampling, complete processes, evaluation, and reporting |
| EN 301 549 | European ICT procurement/accessibility mapping across web, software, documents, hardware, and support services |
| European Accessibility Act and applicable national implementations | Legal-context/profile metadata for covered products and services; legal interpretation remains external |
| Revised Section 508 | US federal ICT procurement/reporting profile |
| ADA and related US legal context | Legal-context metadata; WCAG mapping and qualified legal review rather than automated legal determination |
| India RPwD Act, 2016 | Indian statutory accessibility context |
| GIGW 3.0 | Indian government website/app quality, accessibility, security, and lifecycle profile |
| BIS accessibility standards for ICT products and services, including IS 17802 series | Indian ICT standards mapping beyond web-only checks |
| PDF/UA and applicable document standards | Later document/PDF accessibility profile |
| Platform accessibility guidance from Apple, Google, Microsoft, and relevant native frameworks | Later mobile/native profile requirements |

Reports should state the exact edition and profile used. Standards and laws change; the compliance registry must be updateable without changing historical reports.

### 14.4 Evaluation-method requirements

- Use ACT Rules Format principles for transparent, versioned checks with applicability, assumptions, expectations, and `passed|failed|cantTell|inapplicable` outcomes.
- Use WCAG-EM 2.0 to define the product/website scope, representative samples, complete processes, evaluation procedure, and findings report.
- Use real assistive technologies when a profile requires them; DOM/ARIA inference alone is insufficient.
- Include qualified manual review wherever a criterion is subjective, contextual, or not reliably machine-testable.
- Involve users with disabilities when feasible, with accessible informed consent and institutional ethics approval where required.
- Preserve the difference between a rule result, a journey outcome, a conformance evaluation, and a legal conclusion.

### 14.5 Accessibility-profile roadmap

| Profile | Representative coverage | Current state |
|---|---|---|
| Keyboard motor — desktop web | Sequential focus, activation, traps, order, focus visibility/restoration, custom widgets, errors, timing, full workflows | Current implementation track |
| Screen reader — desktop web | Names, roles, states, reading/announcement order, live regions, forms, dialogs, dynamic updates, AT/browser behavior | Planned after keyboard track |
| Visual/low vision/color | Contrast, zoom, reflow, spacing, focus appearance, non-text contrast, magnification behavior, alternatives | Planned |
| Hearing/multimedia | Captions, transcripts, audio description, media controls, synchronization and quality review | Planned |
| Cognitive/learning | Instructions, consistency, error prevention/recovery, time, accessible authentication, cognitive load and usability | Planned; largely semi-automated/manual |
| Alternative motor input | Switch, speech/voice control, touch, pointer gestures, drag alternatives, target size | Planned |
| Mobile web/native | Platform semantics, focus, gestures, orientation, dynamic text, screen readers, switch control | Planned |
| Documents/PDF | Tags, structure, reading order, alternatives, forms, tables, metadata, PDF/UA mapping | Planned |
| Native desktop | Platform accessibility APIs, keyboard, high contrast, screen readers, scaling | Planned |

### 14.6 India-specific requirements

- The Rights of Persons with Disabilities Act, 2016 provides statutory context for accessibility, including information and communication technology.
- GIGW 3.0 is relevant to Indian government websites and applications and references WCAG 2.1 Level AA alongside quality, security, and lifecycle requirements.
- BIS accessibility standards for ICT products and services should be mapped when the product expands beyond web-only evaluation.
- Reports may offer profiles such as `WCAG 2.2 AA`, `GIGW 3.0 / WCAG 2.1 AA`, or a future BIS/EN 301 549-aligned profile, while retaining criterion-level evidence.
- Legal claims and statutory applicability require qualified review; the platform supplies traceability and evidence rather than legal advice.

### 14.7 Security, privacy, and AI governance

- OWASP ASVS 5.0 Level 2 is the recommended application-security verification baseline.
- OWASP SSRF and GenAI/agent guidance informs URL handling, prompt injection, insecure output handling, excessive agency, and resource controls.
- NIST Secure Software Development Framework informs the secure development lifecycle.
- NIST AI Risk Management Framework provides the lightweight AI governance structure: Govern, Map, Measure, and Manage.
- India's Digital Personal Data Protection Act, 2023 and notified DPDP Rules, 2025 inform notice, purpose, safeguards, processor controls, retention, deletion, and incident handling.
- Payment sandbox integrations must follow provider rules and must never cause the platform to store card data; a later production payment-testing capability would require a specific PCI DSS scope assessment.
- Health, education, financial, government, or other regulated journeys require domain-specific privacy and authorization review before use.

### 14.8 Required disclaimer

Every report must state:

> This report describes observations from the declared journey, accessibility profile, environment, rules, coverage register, and review procedure. It is not a complete accessibility audit or legal advice unless the report explicitly documents a complete qualified conformance-evaluation scope and sign-off. Automated journey results alone do not establish whole-product compliance.

---

## 15. Recommended technology stack

This is the approved Python-first baseline. It favors one coherent modular monolith, an independently scalable browser worker, durable managed data services, and replaceable external adapters. Exact package and browser versions must be pinned in `pyproject.toml`, `uv.lock`, the container image, and CI after a Phase 0 compatibility spike. Use supported stable releases and never hard-code a model that is near deprecation.

### 15.1 Application and user interface

| Concern | Approved technology | Reason |
|---|---|---|
| Language | Python 3.13 on one pinned patch release | Current, strongly supported Python baseline with a large automation ecosystem |
| Web framework | Django 5.2 LTS | Long support window, integrated security, authentication, ORM, migrations, forms, templates, and administration |
| Page rendering | Django Templates | Keeps the primary product in one Python application and produces semantic server-rendered HTML |
| Progressive interaction | HTMX, pinned and self-hosted | Adds partial updates without introducing a second application framework or a TypeScript build dependency |
| Styling | Tailwind CSS with project-owned accessible patterns | Fast, consistent styling while preserving control over native semantics and focus behavior |
| Browser scripting | Minimal vanilla JavaScript in small, audited modules | Used only where HTML and HTMX are insufficient |
| Forms | Django Forms for HTML; DRF serializers for REST | Centralized validation with accessible server-side error handling |
| Live progress | Server-Sent Events with polling fallback | Appropriate for one-way run progress without WebSocket complexity |
| Internal operations | Django Admin with hardened permissions | Provides a mature interface for rules, fixtures, environments, users, and support operations |
| End-to-end tests | Playwright for Python | Verifies the product itself with the same language and keyboard-first discipline |

The product interface must use semantic HTML, landmarks, native controls, explicit labels, useful document titles, predictable focus movement, and accessible validation before adding enhancement. Core actions must remain usable when optional JavaScript fails. Third-party UI component libraries are not part of the initial stack; any later component must pass keyboard, semantics, contrast, reflow, and screen-reader review before adoption. HTMX and other browser assets must be bundled locally rather than loaded from a public CDN.

### 15.2 Django application and REST interface

| Concern | Approved technology | Reason |
|---|---|---|
| Core framework | Django 5.2 LTS | One secure, cohesive application boundary rather than duplicated web stacks |
| REST interface | Django REST Framework | Mature authentication, permissions, serialization, pagination, and test support |
| API schema | drf-spectacular | Versioned OpenAPI generation from DRF endpoints and serializers |
| Persistence | Django ORM and Django migrations | Transactional relational model with one official migration system |
| Boundary validation | Django Forms and DRF serializers | Validate untrusted web input at the application boundary |
| Engine contracts | Pydantic v2 | Typed planner actions, worker messages, configuration, and evidence contracts outside the web boundary |
| Runtime protocol | Django ASGI | Supports async-safe endpoints and streaming while retaining Django's full platform |
| Application server | Uvicorn | Production ASGI process; run behind the hosting platform's TLS proxy/load balancer |
| Human authentication | Django sessions plus standards-based OIDC, using a maintained integration such as `django-allauth` | Secure browser sessions without building password or identity-provider logic |
| Authorization | Django permissions plus explicit project/environment object checks | Enforces tenant and object ownership on every query and artifact access |
| API style | Versioned REST/OpenAPI under `/api/v1/` | Stable external contract for future CI, SDK, and integration clients |

Browser users should use secure, HTTP-only session cookies with CSRF protection. Future non-browser integrations may receive scoped, revocable service credentials, but they must not reuse browser session behavior. Django models are the source of truth for run state. Run creation must write the run and an outbox job record in the same PostgreSQL transaction. An idempotent dispatcher publishes pending outbox records to Celery; `transaction.on_commit()` may wake the dispatcher but is not the sole durability mechanism. This closes the commit/enqueue failure window and prevents a worker from observing an uncommitted run.

#### Outbox recovery contract (`outbox_dispatch.v1`) — resolves AG-001

- A Celery Beat task runs `dispatch_pending_outbox` every 30 seconds; it is the crash-recovery wake-up mechanism, not a convenience feature.
- The dispatcher claims only `pending` records with `next_attempt_at <= now` using a short database transaction and `select_for_update(skip_locked=True)`.
- A claim sets `dispatching`, `lease_expires_at = now + 60 seconds`, and increments `attempt_count`. A stale `dispatching` claim is returned to `pending` by the same periodic task after the lease expires.
- A successful `apply_async` call records the deterministic Celery task ID and sets `dispatched`. `dispatched` means “broker publication was attempted and accepted by the client library,” not “the worker completed the run.” Worker lifecycle remains on `TestRun`.
- If the process dies after publication but before this update, a later retry may publish a duplicate. The worker must conditionally claim `TestRun` from `queued` to `starting`; duplicate task deliveries become no-ops and cannot create a second logical run.
- Failed publication uses exponential retry with `next_attempt_at`; after 12 failed attempts the record is `failed_dispatch` and the run is terminal `system_error` with auditable error metadata.
- Required configuration: `OUTBOX_POLL_INTERVAL_SECONDS=30`, `OUTBOX_DISPATCH_LEASE_SECONDS=60`, and `OUTBOX_MAX_DISPATCH_ATTEMPTS=12`.

### 15.3 Job execution, evaluation engine, and browser automation

| Concern | Approved technology | Reason |
|---|---|---|
| Durable task queue | Celery 5.6.3 with a managed Redis-compatible broker | Mature retries, routing, worker scaling, and operational visibility |
| Durable run state | PostgreSQL through Django models | Queue state is operational; the database remains the authoritative product record |
| Browser automation | Async Playwright for Python | Real browser contexts, keyboard control, tracing, and predictable concurrency |
| Initial browser | Pinned Chromium build installed with Playwright | Reproducible first-browser environment |
| Accessibility scanner | Locally bundled, pinned axe-core | Reproducible scans without CDN or target CSP dependence |
| Planner seam | Internal provider-neutral `Planner` interface | Keeps planning replaceable and independently testable |
| Initial model adapter | Current supported stable Gemini Flash-class model through `google-genai`, selected by configuration | Cost-aware multimodal planning through the maintained SDK |
| Output control | Provider-native structured output plus Pydantic semantic validation | Restricts proposals to typed, bounded actions |
| Execution isolation | Disposable non-root container per run, or an equivalently strong isolated worker slot | Protects the platform from untrusted target content |
| Accessibility profile seam | Versioned profile and rule interfaces | Adds later visual, AT, mobile, document, and native evaluators without rewriting run orchestration |
| Sandbox seam | Typed provider adapters | Supports payment test mode, mail/message sinks, disposable accounts, and cleanup verification |

Django web processes must never launch or wait for Playwright directly. They validate and authorize a request, commit the run and outbox intent, and return promptly. A dispatcher publishes that intent idempotently to Celery. Celery workers execute the run and persist append-only events, heartbeats, results, and artifact metadata. Separate worker queues should be available for browser runs and lightweight dispatch/maintenance jobs so a slow browser cannot starve cleanup or reporting work.

Phase 0 must prove late acknowledgement behavior, visibility timeouts, idempotent retry, cancellation, heartbeat/lease expiry, worker termination, browser-process cleanup, and dead-letter handling. If Celery cannot satisfy the verified contract cleanly, its adapter may change without changing the run-orchestration interface or product API.

### 15.4 Data, storage, and secrets

| Concern | Approved technology | Reason |
|---|---|---|
| Relational database | PostgreSQL 18.6 on a managed service | Durable transactions, JSON support where justified, indexing, reporting, and a long support window |
| Data access | Django ORM | Consistent authorization-aware queries and migrations within the application |
| Queue/cache | Managed Redis-compatible service | Broker, rate limiting, locks, and short-lived coordination only |
| Evidence artifacts | S3-compatible object storage | Durable scalable storage with signed, expiring access |
| Local worker disk | Ephemeral scratch only | Removed at run completion or worker cleanup |
| Secrets | Hosting secret manager/environment injection | Keeps credentials out of source, images, logs, and evidence |
| Test credentials | Short-lived secret references resolved only inside the worker | Prevents raw credentials entering prompts, ordinary database fields, or reports |
| Compliance registry | Versioned Django models seeded from reviewed source data | Preserves standards editions, mappings, coverage states, and historical interpretation |

Use normalized relational tables for identity, projects, environments, journeys, runs, steps, findings, rule versions, and audit events. Use bounded JSON fields only for versioned snapshots or provider-specific payloads whose schema is validated at entry. Do not use Redis as permanent storage. Object keys must be unpredictable, scoped to the owning project/run, encrypted at rest, and served only through short-lived signed URLs after an authorization check.

#### Verified version pins — resolves FG-002

The initial lockfile and Compose configuration must use `celery[redis]==5.6.3` and PostgreSQL `18.6` (for example, an image pinned to the `18.6` release and then to its image digest). Pre-release versions are prohibited. Phase 1A must record `celery --version`, `SELECT version()`, the image digest, and the lockfile hash in the progress log. PostgreSQL 18 is a supported major release through November 2030, and Celery 5.6.3 is the current stable 5.6 patch at this document revision; a later update requires the same compatibility evidence, not an unreviewed floating upgrade.

### 15.5 Infrastructure and operations

| Concern | Approved technology/approach | Reason |
|---|---|---|
| Local development | Docker Compose with Django, worker, PostgreSQL, Redis, and MinIO | Reproducible environment with production-shaped boundaries |
| Packaging | Separate Django web and browser-worker Docker images from one repository | Independent scaling and tighter worker isolation without microservices |
| Initial hosting | Container platform with separate web, worker, PostgreSQL, Redis, and S3-compatible services | Production-shaped deployment without Kubernetes |
| Infrastructure definition | Platform blueprint first; Terraform only when repeated environments justify it | Keeps deployment reviewable without premature infrastructure overhead |
| CI/CD | GitHub Actions or equivalent | Lint, type checks, tests, security scans, image build, migration check, and staging deployment |
| Telemetry | OpenTelemetry-compatible traces/metrics plus structured JSON logs | Correlates web, queue, worker, browser, model, and storage events by run ID |
| Error tracking | Sentry or a compatible hosted/self-hosted alternative | Actionable Django and worker exception visibility |

A managed platform such as Render is acceptable for the initial staging deployment if it provides separate process types and managed data services. Evidence must remain in object storage; do not depend on a container's local filesystem or a single attached disk. The images, configuration, health checks, migrations, and backing-service contracts must remain portable to another standards-compliant container platform.

### 15.6 Developer tooling and quality gates

- Environment and dependencies: `uv`, `pyproject.toml`, and a committed `uv.lock`.
- Formatting and linting: Ruff, enforced locally and in CI.
- Static type checking: Pyright, with strictness increased module by module and no silent blanket exclusions.
- Tests: pytest, pytest-django, pytest-playwright, pytest-cov, and pytest-asyncio only where async unit tests require it.
- Web/API tests: Django test client and DRF `APIClient` for permissions, validation, transactions, and schemas.
- Asset build: a minimal pinned Node runtime only for compiling Tailwind and vendored browser assets; Node is not an application runtime.
- Pre-commit: formatting, linting, migration drift, secret detection, and fast unit tests.
- Security gates: dependency audit, secret scan, static analysis, container scan, Django deployment checks, and authorization regression tests.
- Reproducibility: pinned Python, browser, axe-core, model configuration, containers, and fixture versions recorded with every release.

### 15.7 Explicitly rejected for the initial implementation

The initial implementation must not add React, Next.js, TypeScript application code, Vite, FastAPI as a second web framework, SQLAlchemy, Alembic, MongoDB, LangChain-style orchestration frameworks, Streamlit/Gradio, Kubernetes, or separately deployed microservices. These choices would duplicate capabilities, split validation and authorization across stacks, or add operations cost without solving a current requirement. A future ADR may revisit a choice only when measured constraints show that the approved stack cannot meet a defined requirement.

---

## 16. Logical architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Django ASGI Web Application                                 │
│ Templates + HTMX · REST/OpenAPI · SSE · Admin              │
│ Auth · Authorization · Validation · Runs · Reports          │
└──────────────────────────┬──────────────────────────────────┘
                           │ atomic run + outbox transaction
                           v
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL 18                                               │
│ users · projects · runs · outbox · events · findings        │
└──────────────────────────┬──────────────────────────────────┘
                           │ pending outbox records
                           v
┌─────────────────────────┐       ┌───────────────────────────┐
│ Idempotent Dispatcher   │──────▶│ Celery / Redis broker    │
│ publish · retry         │       │ routes · retries · DLQ   │
└─────────────────────────┘       └─────────────┬─────────────┘
                                               │
                                               v
                              ┌────────────────────────────────┐
                              │ Isolated Celery Browser Worker │
                              │ Evaluation Engine              │
                              │ Observer · Planner · Policy    │
                              │ Executor · Rules · Evidence    │
                              │ Async Playwright · Chromium    │
                              │ local axe-core                 │
                              └──────────┬──────────────┬──────┘
                                         │              │
                                artifacts│              │typed request
                                         v              v
                         ┌────────────────────┐  ┌────────────────────┐
                         │ S3 object storage  │  │ Configured LLM     │
                         │ screenshots/traces │  │ structured action  │
                         └────────────────────┘  └────────────────────┘

All components emit correlated, redacted telemetry.
```

### Architectural style

Use a Django modular monolith for the product and a separately deployable Celery browser worker from the same repository. The web and worker processes share domain contracts and persistence models but have different entry points, permissions, resource limits, and scaling policies. Do not create additional network services until a measured requirement justifies a new operational boundary.

### Key modules, interfaces, and replaceable seams

The architecture should use deep modules: each module exposes a small stable interface while hiding implementation and provider complexity.

| Module | Stable interface | Hidden implementation / adapters |
|---|---|---|
| Product application | HTML/HTMX views, `/api/v1/`, SSE events, admin operations | Django views, forms, DRF serializers/viewsets, templates, permissions |
| Run orchestration | Create, authorize, record job intent, dispatch, cancel, heartbeat, append event, finish, retry | Django transaction/outbox models plus Celery/Redis adapter |
| Evaluation engine | `execute(journey, profile, environment) -> events + RunResult` | Observation, planning, policy, keyboard execution, detectors, cleanup |
| Planner | Typed `propose_next_action(observation, goal, history)` | Gemini adapter and deterministic fake for tests |
| Artifact store | Put, retrieve by authorized signed URL, retain, delete | S3 adapter; MinIO adapter in local development |
| Secret resolver | Resolve a short-lived secret reference for an authorized run | Deployment/provider secret-manager adapter |
| Sandbox integration | Prepare, assert expected effect, clean up | Payment, mail, messaging, upload, and disposable-account adapters |
| Accessibility profile | Rules, allowed actions, evidence requirements, outcome policy | Keyboard profile now; later AT, visual, cognitive, media, mobile, and document profiles |

Tests must exercise the same interfaces used in production. Fakes belong behind these seams rather than being implemented as special-case branches in domain logic.

---

## 17. Planned repository structure

```text
accesspath-ai/
├── config/                    # settings, ASGI, URLs, Celery bootstrap
│   └── settings/              # base, local, test, production
├── apps/                      # Django product/domain modules
│   ├── accounts/              # identity, membership, OIDC integration
│   ├── projects/              # tenant/project ownership boundary
│   ├── environments/          # targets, authorization, execution policy
│   ├── journeys/              # goals, fixtures, test-data references
│   ├── runs/                  # lifecycle, events, orchestration interface
│   ├── findings/              # normalized findings and mappings
│   ├── compliance/            # standards profiles and coverage registry
│   ├── artifacts/             # metadata, signed access, retention/deletion
│   ├── reports/               # report assembly and export
│   └── audit/                 # security and administrative audit events
├── engine/                    # framework-light evaluation package
│   ├── contracts/             # Pydantic actions, observations, results
│   ├── observer/
│   ├── planner/               # interface, Gemini adapter, deterministic fake
│   ├── policy/
│   ├── executor/
│   ├── detectors/
│   ├── profiles/              # keyboard now; later profiles by version
│   ├── sandbox_adapters/      # payment, mail, messaging, upload, cleanup
│   └── evidence/
├── workers/                   # Celery tasks and process entry points
├── templates/                 # semantic Django templates
├── static_src/                # Tailwind source and minimal browser scripts
├── static/                    # collected/versioned generated assets
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   └── e2e/
├── fixtures/                  # accessible/broken benchmark applications
├── evaluation/                # protocols, labels, metrics, analysis scripts
├── docs/
│   ├── adr/                   # durable architecture decisions only
│   ├── threat-model.md
│   └── api/                   # exported OpenAPI/report schemas
├── infrastructure/            # containers and deployment definitions
├── manage.py
├── pyproject.toml
├── uv.lock
├── .github/workflows/         # or equivalent CI configuration
├── ACCESSPATH_AI_MASTER_PROJECT_PLAN.md
└── README.md                  # short setup entry point created in Phase 1
```

Begin with one monorepo so migrations, engine contracts, fixtures, and versioned evaluation assets change atomically. Django apps may depend on small shared domain contracts, but they must not import another app's views, serializers, templates, or internal implementation. The `engine/` package must not depend on HTTP requests or template rendering; it receives validated contracts and emits typed events/results. The `workers/` layer is the adapter between Celery/Django persistence and that engine.

---

## 18. Data model

### 18.1 Main entities

**User**

- Identity of a person using the platform.
- References an external OIDC subject.

**Project/Tenant**

- Ownership boundary for targets, journey specifications, runs, and artifacts.

**Accessibility Profile**

- Versioned declaration of user needs, input/output methods, assistive technologies, platforms, rules, evidence requirements, and supported claims.

**Compliance Profile and Requirement**

- Versioned standards or regulatory profile with criterion-level applicability, mappings, coverage state, rule/review protocol, and authoritative source metadata.

**Target**

- Normalized origin.
- Authorization status and verification evidence.
- Allowed related origins and policy settings.

**Test Environment**

- Owner-authorized target configuration.
- Execution mode, allowed side effects, test-data policy, sandbox integrations, credential references, reset/cleanup behavior, and expiry.

**Test Identity and Data Set**

- Synthetic user/persona and controlled inputs used by a journey.
- References secrets rather than storing passwords, tokens, payment test values, or inbox credentials directly.

**Journey Specification**

- Accessibility profile and test-environment version.
- Start URL.
- Task goal.
- Controlled inputs and test-identity reference.
- Completion signals.
- Execution mode and allowed side effects.
- Allowed origin scope.
- Cleanup and rollback assertions.
- Version and creator.

**Test Run**

- Immutable execution identifier.
- Journey specification version.
- Infrastructure run state.
- Journey outcome.
- Environment and configuration versions.
- Parent run for reruns.
- Timing, limits, and terminal reason.

**Job Outbox Record**

- Created atomically with the Test Run.
- Stable idempotency key, task type, run reference, payload schema version, and routing key.
- Pending, dispatched, attempt-count, next-attempt, and last-error metadata.
- Retained long enough to audit and reconcile delivery without becoming the run-state source of truth.

**Step**

- Sequence number.
- Observation summary.
- proposed/validated/executed action.
- before and after fingerprints.
- action effect.
- timing.
- planner and policy metadata.

**Rule Definition**

- Stable identifier and version.
- Applicability, assumptions, expectation, outcome rules, and standards mappings.

**Rule Evaluation**

- Rule version.
- Step/checkpoint.
- Outcome: `passed`, `failed`, `cantTell`, or `inapplicable`.
- Evidence references.

**Finding**

- Normalized finding type.
- Severity and task impact.
- Verification/review status.
- Component fingerprint and locator bundle.
- Reproduction instructions.
- standards mappings.

**Side Effect and Cleanup Record**

- Expected and observed state changes produced by a controlled transactional journey.
- Cleanup attempt, verification status, operator action, and audit history.

**Baseline Observation**

- Comparator and version.
- Browser checkpoint.
- Raw rule identifier and normalized mapping.

**Artifact**

- Object-storage key.
- MIME type, byte size, cryptographic digest.
- redaction state.
- retention/deletion time.
- access classification.

**Run Event**

- Append-only lifecycle and audit event used for progress, recovery, and investigation.

**Manual Review**

- Structured reviewer answers, reviewer role, evidence, adjudication, and sign-off for semi-automated or manual compliance coverage.

### 18.2 Status separation

Infrastructure lifecycle and evaluation outcome must remain separate.

**Run state**

```text
queued → starting → running → finalizing → succeeded
                                  ├──────→ failed
                                  └──────→ cancelled
```

**Journey outcome**

```text
completed | blocked | inconclusive | environment_blocked | safety_stopped | cleanup_failed
```

A run can be technically successful while the journey is blocked or inconclusive. A system failure must not be reported as an accessibility barrier.

### 18.3 Data design rules

- Use UUID or equivalent non-sequential public identifiers.
- Use timezone-aware timestamps.
- Store durations as integer milliseconds.
- Scope every owned entity to a project/tenant.
- Use constraints and enumerations for state transitions.
- Keep test-run results immutable.
- Use new runs and report revisions instead of overwriting history.
- Store large evidence outside PostgreSQL.
- Store sanitized, size-limited element context rather than full raw HTML.
- Record browser, model, prompt, policy, rule, scanner, and benchmark versions.
- Store standards mappings as versioned many-to-many relationships.
- Never store raw credentials or real payment data in journey, step, event, artifact, or report records.
- Preserve the exact accessibility profile, compliance profile, and coverage-register versions used by a report.
- Make cleanup failures operationally visible and prevent silent reuse of a contaminated test environment.

---

## 19. API plan

### 19.1 Core endpoints

```text
POST   /api/v1/runs/
GET    /api/v1/runs/{run_id}/
GET    /api/v1/runs/{run_id}/events/
POST   /api/v1/runs/{run_id}/cancel/
GET    /api/v1/runs/{run_id}/report/
GET    /api/v1/runs/{run_id}/artifacts/{artifact_id}/
POST   /api/v1/runs/{run_id}/reruns/
GET    /api/v1/runs/
DELETE /api/v1/runs/{run_id}/
POST   /api/v1/environments/
GET    /api/v1/environments/{environment_id}/
POST   /api/v1/environments/{environment_id}/verify/
POST   /api/v1/environments/{environment_id}/reset/
GET    /api/v1/accessibility-profiles/
GET    /api/v1/compliance-profiles/
GET    /api/v1/compliance-profiles/{profile_id}/coverage/
GET    /api/v1/rules/
GET    /api/v1/health/live/
GET    /api/v1/health/ready/
```

### 19.2 API behavior

- `POST /api/v1/runs/` returns `202 Accepted` after the run and outbox intent commit atomically; dispatch may occur immediately afterward.
- Run creation supports an idempotency key.
- Outbox dispatch and worker execution are idempotent so at-least-once delivery cannot create a second logical run or duplicate terminal effects.
- Lists use cursor pagination and filtering.
- Errors use one versioned machine-readable envelope.
- Cancellation is a request with explicit terminal semantics.
- Artifact access uses authorization plus short-lived signed delivery.
- Report schemas are versioned.
- OpenAPI is generated and checked in CI for breaking changes.
- Authentication does not replace object-level authorization.
- Per-user, per-project, and per-origin limits are enforced.
- Secret values are written only to the configured secret manager; the API stores opaque references.
- State-changing execution requires a verified environment, explicit allowed-effects policy, and cleanup configuration.
- Compliance coverage responses expose implemented, manual, planned, unsupported, and not-applicable states without presenting planned coverage as current capability.

---

## 20. Report specification

### 20.1 Summary

- Task goal.
- Target and allowed scope.
- Accessibility profile, compliance profile, and execution mode.
- Journey outcome.
- Start/end time and duration.
- Browser, viewport, locale, and versions.
- Number of actions, findings, needs-review observations, and baseline observations.
- Clear non-certification disclaimer.
- Coverage summary showing automated, semi-automated, manual, AT-required, planned, unsupported, and not-applicable requirements.
- Expected/observed side effects and cleanup status for controlled transactional journeys.

### 20.2 Journey timeline

For every meaningful step:

- step number and time;
- current URL and checkpoint;
- focused component summary;
- executed keyboard action;
- observed effect;
- screenshot/trace reference where retained; and
- applicable rule evaluations.

### 20.3 Finding card

- Finding identifier and title.
- Status: verified, needs review, dismissed, or resolved in a later rerun.
- Task impact and severity.
- Barrier mechanism.
- Exact reproduction steps.
- Component locator bundle and sanitized context.
- Before/after evidence.
- Standards references.
- Affected interaction profile.
- Suggested remediation, clearly labeled as guidance.
- Baseline comparison.

### 20.4 Baseline comparison

Do not compare raw issue counts as if they were equivalent. Present:

- verified barriers found by both approaches;
- verified journey barriers not reported by axe at the matched states;
- axe observations unrelated to the tested journey;
- findings needing human review; and
- unsupported or untested conditions.

### 20.5 Rerun comparison

- Resolved findings.
- Persistent findings.
- New findings.
- Incomparable findings caused by changed environment or journey.
- Outcome, duration, and action-count differences.

### 20.6 Compliance coverage appendix

Every report generated under a standards profile should include:

- exact profile and edition;
- applicable criterion or clause;
- coverage state;
- rule or review-protocol version;
- result and supporting evidence;
- reviewer/AT environment where required;
- untested or unsupported criteria;
- limitations and assumptions; and
- whether the document is a journey report, partial evaluation, or complete qualified conformance evaluation.

Future legal or procurement exports may format this information for a specific jurisdiction, but must not transform missing coverage into a pass.

---

## 21. Security and responsible-use design

### 21.1 Target authorization

- Default to team-owned fixtures and staging sites.
- Require an authorization attestation for every target.
- Use a domain allowlist for the course deployment.
- Add stronger domain verification before supporting broader public testing.
- Respect site policy and stop when automation is blocked.
- Do not implement stealth or anti-bot evasion.

### 21.2 SSRF and network controls

- Accept only approved `https` targets for the deployed MVP.
- Reject embedded credentials, unsupported schemes, and disallowed ports.
- Resolve hostnames and block loopback, private, link-local, multicast, reserved, and metadata-service ranges for IPv4 and IPv6.
- Revalidate every redirect and connection.
- Mitigate DNS rebinding.
- Restrict worker egress to approved target and required service endpoints.
- Limit redirects, response size, request count, downloaded bytes, pages, actions, duration, memory, and CPU.
- Block downloads, file URLs, local schemes, browser extensions, unnecessary permissions, and unexpected new origins.

### 21.3 Browser isolation

- Use a fresh disposable browser context for each run.
- Run the browser as a non-root user with Chromium sandbox and restrictive container profile.
- Provide no host mounts, cloud instance credentials, database credentials, or other users' storage.
- Delete cookies, storage, downloads, and scratch files at the end of the run.
- Terminate all browser child processes on cancellation or worker failure.

### 21.4 Prompt injection and agent control

- Treat all page text, attributes, pixels, and metadata as untrusted content.
- Never allow page content to redefine the task goal, policy, or system instructions.
- Give the model only the bounded action schema.
- Authorize every proposed action with deterministic policy code.
- Keep secrets and internal system information out of model context.
- Test hidden text, hostile instructions, misleading UI, and data-exfiltration attempts in the controlled fixtures.

### 21.5 Side-effect policy

Complete journeys are supported through three explicit execution modes.

**Observe-only mode**

- Suitable for public or production targets with limited authorization.
- May navigate, fill non-sensitive synthetic values where permitted, and reach the final review step.
- Stops before purchase, booking confirmation, account creation, message transmission, application submission, consent acceptance, upload, deletion, or any other externally visible effect.
- Produces `safety_stopped` when the next required action exceeds policy.

**Sandbox-transactional mode**

- Required for full account, authentication, booking, checkout/payment, messaging, upload, consent, and destructive-action journeys during development and routine testing.
- Runs only in an owner-controlled fixture, staging system, payment-provider test mode, test inbox/mail sink, test messaging sink, or disposable tenant/account.
- Uses synthetic identities and non-sensitive generated files.
- Declares expected effects and cleanup/rollback assertions before execution.
- Verifies cleanup and produces `cleanup_failed` if the environment cannot be restored.

**Approved production-audit mode**

- A future restricted mode for a target owner with explicit scope, named approver, maintenance window, test identities, recipient/payment safeguards, rate limits, incident contact, and cleanup plan.
- High-impact actions require an additional human approval checkpoint.
- Real charges, real applications, real medical/legal commitments, and messages to uncontrolled recipients remain prohibited.

Credentials, identity documents, payment details, health data, and other sensitive values must not be exposed to the planner. Payment journeys use provider sandbox tokens or test cards and keep AccessPath AI out of cardholder-data storage.

### 21.6 Application security

- Use OIDC and secure HTTP-only session handling.
- Enforce authorization on every run, report, and artifact.
- Protect against IDOR, stored XSS from hostile DOM/model output, CSRF where applicable, injection, insecure deserialization, and excessive resource use.
- Rate-limit and quota expensive operations.
- Redact sensitive values from logs.
- Use dependency and container scanning in CI.
- Maintain an incident-response and key-rotation procedure.

---

## 22. Privacy and data governance

Potentially sensitive data includes URLs, screenshots, DOM excerpts, visible text, form inputs, cookies, prompts, logs, traces, and model responses.

### Required controls

- Use synthetic form data.
- Use opaque secret references for authentication fields and resolve them only inside the isolated worker.
- Permit only provider test values for payment fields and keep them out of prompts, logs, screenshots where feasible, and permanent records.
- Block real identity, health, education, financial, and payment data unless a later approved profile has a documented lawful basis and protection plan.
- Capture the smallest useful page excerpt.
- Crop or redact screenshots where practical.
- Redact likely secrets and personal data before persistence and model transmission.
- Never retain full page HTML by default.
- Encrypt transport and managed storage.
- Use tenant-scoped object keys and signed access.
- Record artifact access.
- Define a short default evidence-retention period, initially 7–30 days.
- Support user-requested deletion and verified deletion jobs.
- Document model/storage providers and retention behavior.
- Disable provider training/storage of evidence where configuration permits.
- Keep a data inventory and incident-response procedure.

If people with disabilities are recruited for the academic evaluation, obtain free and informed consent in accessible formats and follow the institution's research/ethics requirements before recruitment.

---

## 23. Non-functional requirements

### Reliability

- Accepted runs must be durably stored before the API responds.
- Worker jobs use leases/heartbeats and bounded retry.
- Retries must be idempotent.
- Transient platform failures must be distinguished from repeatable accessibility outcomes.
- Cancellation must stop the browser and release resources.
- Failed artifact upload must not produce a successful final report.

### Performance

- Run creation should return promptly after the atomic run/outbox commit; dispatch latency must be measured.
- Progress should update without reloading the page.
- Action and duration budgets must be configurable.
- Queue delay, browser startup, model latency, scan time, and upload time must be measured separately.

### Scalability

- API instances must remain stateless apart from external stores.
- Browser workers must scale independently.
- Artifacts must not depend on one server's disk.
- Per-origin and global concurrency must be controllable.
- Backpressure must be visible through queue metrics and user-facing status.

### Maintainability

- Typed Python boundaries using Pyright and Pydantic contracts.
- Versioned schemas and rules.
- Clear module boundaries.
- One committed Python dependency lockfile plus pinned browser/asset versions.
- Automated migrations and rollback plans.
- Small Architecture Decision Records only for costly, surprising trade-offs.

### Accessibility of AccessPath AI

- The product interface itself targets WCAG 2.2 AA.
- All product journeys must be usable with the same keyboard profile.
- Progress updates must be accessible without stealing focus.
- Error messages must be programmatically associated and keyboard reachable.
- Color must not be the only result indicator.
- Manual keyboard evaluation of the product is part of every milestone.

### Observability

- Every request, job, run, step, and artifact uses correlated identifiers.
- Logs are structured and redacted.
- Metrics include queue depth, queue delay, run duration, outcomes, retries, browser crashes, invalid model actions, cost, and result consistency.
- Traces cover API, queue, worker, model request, scanner, and artifact upload.
- Health and readiness endpoints distinguish liveness from dependency readiness.

---

## 24. Functional requirements

### Must have

| ID | Requirement |
|---|---|
| FR-001 | A user can create a run from an approved URL, task goal, and synthetic inputs |
| FR-002 | The Django application validates authorization, URL safety, input size, and target policy before recording a job intent |
| FR-003 | An idempotent outbox dispatcher and durable worker execute the run independently of the web process |
| FR-004 | The worker uses only the declared keyboard profile for interaction |
| FR-005 | Every proposed action is schema-validated and policy-authorized |
| FR-006 | The observer records before/after state for every executed action |
| FR-007 | Versioned rules evaluate the supported detector catalogue |
| FR-008 | axe-core scans run from a pinned local dependency at defined checkpoints |
| FR-009 | The system supports completed, blocked, and inconclusive outcomes |
| FR-010 | Evidence artifacts are stored durably with authorized access and retention metadata |
| FR-011 | The UI shows live progress and supports cancellation |
| FR-012 | The final report separates journey findings, needs-review items, and baseline observations |
| FR-013 | A rerun creates a new immutable run linked to the earlier run |
| FR-014 | The system compares rerun findings without rewriting the original result |
| FR-015 | The system records versions needed to reproduce the evaluation |
| FR-016 | A project can define and verify an authorized test environment and execution mode |
| FR-017 | Test credentials and sandbox tokens are referenced through a secret manager and never exposed to the planner or report |
| FR-018 | The keyboard track supports controlled authenticated and state-changing journeys with expected-effect and cleanup assertions |
| FR-019 | Controlled fixtures cover account creation, authentication, password recovery, booking, checkout/payment test mode, forms, messaging, uploads, consent, and destructive actions |
| FR-020 | The platform maintains versioned accessibility and compliance profiles with criterion-level coverage states |
| FR-021 | Reports distinguish automated, semi-automated, manual, AT-required, planned, unsupported, and not-applicable coverage |
| FR-022 | Reviewers can complete structured manual or assistive-technology protocols when a requirement cannot be automated |
| FR-023 | New accessibility profiles can reuse the shared journey, evidence, rule, report, and evaluation infrastructure |
| FR-024 | The system records side effects and verifies cleanup for sandbox-transactional runs |

### Should have

| ID | Requirement |
|---|---|
| FR-101 | A user can save and reuse a journey specification |
| FR-102 | Reports can be exported as structured JSON and printable HTML/PDF |
| FR-103 | Reviewers can confirm, dismiss, or mark a finding for follow-up |
| FR-104 | A project can configure retention within allowed limits |
| FR-105 | The dashboard supports filtering by target, outcome, date, and finding type |

### Planned project-wide capabilities after the keyboard core

- Multi-browser workers.
- CI pull-request integration.
- Team roles and approvals.
- Scheduled regression journeys.
- Screen-reader and accessibility-API profiles.
- Visual, multimedia/hearing, cognitive, alternative-input, mobile, document, and native profiles.
- Regulatory/procurement exports for supported compliance profiles.
- API/SDK for external systems.

---

## 25. Evaluation methodology

### 25.1 Research question

> Can a constrained, goal-directed keyboard agent identify reproducible task-level barriers that are not reported by a matched axe-core scan, while maintaining acceptable precision, false-completion rate, and run-to-run consistency?

### 25.2 Evaluation corpus

Use two layers.

**Layer A — controlled benchmark**

- Self-host accessible and deliberately broken variants.
- Cover every supported detector.
- Include at least three variants for each failure mechanism where time permits.
- Include negative controls that resemble failures but are valid behavior.
- Version fixtures and labels in the repository.
- Maintain a held-out evaluation split not used for prompt/rule tuning.

**Layer B — authorized real-world journeys**

- Use team/institution-owned sites, official test sites, or sites with written authorization.
- Select representative sectors such as healthcare, commerce, government, education, and SaaS only when permission and safe task boundaries exist.
- Define exact start and completion boundaries.
- Use observe-only mode on public targets; use sandbox-transactional mode to evaluate complete authenticated and state-changing flows.
- Record and verify expected cleanup for every transactional evaluation.
- Record the evaluation date and environment.

### 25.3 Ground-truth process

1. Write a manual keyboard protocol before evaluation.
2. Two trained reviewers independently execute and label each held-out journey.
3. Reviewers record `passed`, `failed`, `cantTell`, or `inapplicable` for each rule.
4. Disagreements are adjudicated with a documented reason.
5. Report inter-rater agreement.
6. Where feasible, involve an accessibility expert or keyboard user under appropriate consent and ethics review.

#### Evaluation freeze and staffing rule — resolves TP-004

Before manual labeling begins, tag an `evaluation-candidate` revision and freeze feature work on that revision. Members A and C perform independent labels in separate sessions; Member B prepares the frozen benchmark manifest, computes agreement/confusion matrices, and does not alter rules, prompts, fixtures, or labels. Any defect discovered during labeling is recorded, fixed only on a `post-evaluation` branch, and evaluated in a later benchmark round. This prevents the three-person team from simultaneously changing the system and its ground truth.

### 25.4 Baselines

Compare:

1. axe-core at every distinct matched state;
2. deterministic scripted keyboard journeys on controlled fixtures;
3. independent manual keyboard evaluation; and
4. the complete AccessPath AI goal-driven run.

### 25.5 Metrics

- Barrier-event precision, recall, and F1.
- Journey-outcome agreement.
- False completion rate.
- False blocking rate.
- Exact-step or within-one-action blocker localization.
- `needs_review` and inconclusive rates.
- Repeated-run outcome consistency over at least three runs.
- Median and p95 duration.
- Action count to completion or blocker.
- Model tokens and estimated cost per journey.
- Per-detector results.
- Verified journey blockers not reported by matched axe scans.
- Confusion matrix and confidence intervals where sample size permits.

### 25.6 Fair comparison rules

- Use the same URL, state, browser, viewport, and date where possible.
- Do not compare one final axe scan with an entire dynamic journey.
- Deduplicate multiple nodes that represent one barrier mechanism.
- Do not count ambiguous observations as correct failures.
- Publish negative and inconclusive results.
- Freeze model, prompt, rule, browser, and fixture versions before held-out evaluation.

---

## 26. Novelty and academic contribution

### Defensible novelty statement

> AccessPath AI investigates whether bounded, goal-directed keyboard navigation can produce reproducible **task-level barrier localization evidence**—the exact journey step, failed interaction, state transition, and supporting artifact—when compared with matched automated scans, scripted multi-state keyboard tests, and manual keyboard ground truth.

Natural-language goals and AI-guided browser navigation have prior art; ordinary accessibility tools can also be run at multiple scripted states. The primary contribution claim is therefore not “journeys instead of pages,” but evidence-backed localization and uncertainty reporting for an unfamiliar, keyboard-only journey without a pre-authored DOM-specific script.

#### Literature-positioning matrix — resolves UG-001 and UG-002

Before Phase 5 results are written, maintain `literature_positioning.v1` with one row per source and these fields: `source_id`, `citation`, `source_type`, `year_or_version`, `task_scope`, `scripted_or_goal_driven`, `dynamic_state_support`, `accessibility_rules_or_oracle`, `evidence_output`, `known_limitations`, and `comparison_relevance`. The initial matrix must cover at least axe-core, IBM Equal Access Checker, WAVE, Pa11y, Playwright accessibility/snapshot testing, WebArena, Mind2Web, WebVoyager, and one peer-reviewed dynamic-web accessibility-testing study. Every novelty sentence in the proposal, report, or presentation must cite a row in this matrix or be removed.

### What should not be claimed

- “The only tool in existence.”
- “Every existing accessibility tool is static.”
- “Axe fundamentally cannot test dynamic states.”
- “The system proves WCAG compliance.”
- “ARIA checks prove screen-reader compatibility.”
- “Any lack of page change is an accessibility failure.”

### Potential demonstrated contributions

- User-authored task goals without hand-written test scripts.
- Strict keyboard action enforcement.
- Open, versioned controlled benchmark.
- Evidence-backed blocker localization.
- Explicit uncertainty and human-review outcomes.
- Fair comparison with per-state automated scans.
- Immutable rerun comparison after remediation.
- Safety policy for non-destructive evaluation.

The project should defend novelty through measured results and reproducibility rather than market superlatives.

---

## 27. Testing strategy

### Unit tests

- URL parsing, DNS/IP classification, redirect policy, and origin policy.
- Action schema and semantic validation.
- Safety-policy decisions.
- State fingerprints and diffing.
- Detector applicability and outcomes.
- Goal predicates.
- Data redaction.
- Status transitions and retry classification.
- Report normalization and standards mapping.
- Authorization and signed artifact access.

### Integration tests

- Django ORM transactions and migrations against PostgreSQL.
- Django/DRF run creation, authorization, atomic outbox persistence, and dispatcher recovery after publish failure.
- Generated OpenAPI contract and serializer compatibility.
- Worker lease, heartbeat, retry, and cancellation.
- Worker to object storage.
- Planner structured output and invalid-response handling.
- Local axe execution at dynamic checkpoints.
- Full detector behavior on controlled fixtures.

### End-to-end tests

- Create run → progress → final report.
- Cancellation.
- API restart while run is queued/running.
- Worker crash and bounded retry.
- Rerun and comparison.
- Deletion and artifact expiry.
- Cross-user access denial.
- AccessPath AI's own keyboard journey.

### Security tests

- Private/loopback/link-local/metadata destinations.
- Redirect and DNS-rebinding attempts.
- Hostile DOM and stored XSS payloads in reports.
- Hidden prompt injection.
- Unexpected origins, downloads, popups, and schemes.
- Resource-exhaustion pages.
- Invalid or unsafe planner actions.
- Tenant/object authorization.
- Sensitive-data redaction.

### Evaluation regression tests

- Every supported detector has accessible and broken fixtures.
- Every false-positive fix adds a negative-control fixture.
- Model/prompt changes run the complete offline benchmark.
- Browser/axe upgrades require benchmark comparison before release.

---

## 28. Development phases and schedule

### Scheduling convention

**Day 0 is the day the team approves this master plan.** Phase 0 begins immediately. Calendar dates can be added when the course schedule is confirmed, but the sequence and exit gates should not change casually.

### Phase 0 — Specification and safety gate

**Suggested duration:** 3–5 working days  
**Purpose:** Freeze the MVP and remove ambiguity before coding.

Deliverables:

- Team approval of this document.
- Final first-demo detector list.
- Threat model and data-flow diagram.
- Target authorization and action-safety policies.
- Journey, action, finding, report, and evidence schemas.
- Controlled-fixture backlog.
- Short compatibility spike for Playwright, local axe-core, queue cancellation, object storage, and structured model output.
- Architecture decisions for queue, artifact storage, authentication, and deployment.

Exit criteria:

- Every MVP claim maps to an implementation requirement and evaluation method.
- Every automatic failure has a defined evidence rule.
- Ambiguous cases have a `needs_review` or inconclusive path.
- No allowed action can cause an unapproved real-world side effect.
- The team accepts the baseline stack or records an approved replacement.

### Phase 1 — Deterministic keyboard kernel

**Suggested duration:** 1.5–2 weeks  
**Purpose:** Prove reliable observation and evaluation without an LLM.

Build:

- Django project, modular app skeleton, settings separation, and CI.
- Docker Compose development environment with PostgreSQL, Redis, and MinIO.
- Semantic Django template shell, HTMX integration, and accessible navigation.
- Django Admin baseline for controlled operational data.
- Controlled fixture application.
- Playwright observer and keyboard executor.
- State fingerprints and evidence bundle.
- Pinned local axe-core scans.
- KBD-001 through KBD-004 detectors.
- Deterministic scripted journeys.

Exit criteria:

- Accessible and broken fixture variants produce expected outcomes.
- A legitimate modal loop is not mislabeled as a trap.
- Repeated runs generate equivalent evidence.
- No mouse or bypass action appears in the execution trace.

### Phase 2 — Durable platform vertical slice

**Suggested duration:** 1–1.5 weeks  
**Purpose:** Make execution deployable and restart-safe.

Build:

- Django/DRF `/api/v1/runs/` endpoints and generated OpenAPI schema.
- PostgreSQL 18 schema through Django models and migrations.
- Transactional run creation with an idempotent outbox dispatcher to Celery.
- Celery 5.6/Redis job pipeline with separate browser and maintenance queues.
- Worker leases, heartbeat, retry, and cancellation.
- Object-storage artifacts.
- SSE progress.
- Django session/CSRF security, OIDC integration, and object-level authorization.
- Initial staging deployment and telemetry.

Exit criteria:

- `POST /api/v1/runs/` returns a run ID only after the run and outbox intent commit together.
- Restarting the Django web process does not lose the job.
- Worker failure creates bounded retry or an explicit terminal system state.
- Artifacts remain available across deployment.
- Cross-user report/artifact access is denied.

### Phase 3 — Bounded goal-driven planner

**Suggested duration:** 1–1.5 weeks  
**Purpose:** Add natural-language navigation without weakening evidence quality.

Build:

- Provider-neutral planner interface.
- Current supported model integration.
- Structured action output and semantic validation.
- Prompt and policy versioning.
- Explicit completion signals and goal oracle.
- Loop detection based on state/action sequences.
- Token, action, time, and cost budgets.
- Prompt-injection and excessive-agency fixtures.

Exit criteria:

- Planner cannot perform an operation outside the keyboard profile.
- Hostile page text cannot change the goal or policy.
- Invalid output is safely rejected and recorded.
- Ambiguous completion produces `inconclusive`.

### Phase 4 — Product UI and report experience

**Suggested duration:** 1–1.5 weeks  
**Purpose:** Make the system useful and understandable to developers.

Build:

- Run creation interface.
- Live accessible progress page.
- Timeline and finding cards.
- Baseline comparison.
- Evidence authorization and display.
- Rerun and comparison flow.
- Structured export and printable report.
- Manual keyboard evaluation of the product UI.

Exit criteria:

- Every finding links to reproducible evidence.
- Report language never implies whole-site conformance.
- Progress announcements do not steal focus.
- The product's main journey is keyboard operable.

### Phase 5 — Benchmark, evaluation, and hardening

**Suggested duration:** 2 weeks  
**Purpose:** Produce the academic result and strengthen deployment reliability.

Perform/build:

- Complete versioned controlled benchmark.
- Held-out fixture split.
- Controlled keyboard journeys for registration, authentication/recovery, booking, payment-sandbox checkout, forms, messaging, uploads, consent, and cleanup.
- Authorized real-world sample.
- Independent manual labels and adjudication.
- Three repeated runs per evaluation journey.
- Baseline comparison and metrics.
- Error analysis and limitations.
- Load, security, failure-recovery, backup, and restore tests.
- Final documentation, presentation, demo script, and report material.

Exit criteria:

- Evaluation is reproducible from a tagged release.
- Metrics and raw confusion matrix are available.
- Negative, ambiguous, and failed runs are documented honestly.
- Security and privacy checklist is complete for the chosen deployment.
- At least one authenticated journey and representative state-changing sandbox journeys complete end to end and verify cleanup.
- The compliance register accurately separates current keyboard coverage from manual and later-profile coverage.

### Phase 6 — Continued full-project roadmap

Phase 6 is not a rejection of broader accessibility scope. It is the staged continuation after the keyboard-first course core is stable.

**6A — Keyboard platform expansion**

- Firefox and WebKit keyboard profiles.
- Reusable authenticated owner-controlled environments.
- Larger libraries of booking, commerce, financial-test, education, government-form, healthcare-test, messaging, upload, and account-management journeys.
- CI/pull-request integration, scheduled regression monitoring, team roles, approvals, and policy governance.

**6B — Screen-reader and visual accessibility**

- Real accessibility API capture.
- Declared NVDA/JAWS/VoiceOver/TalkBack and browser/platform matrices.
- Reading and announcement order, names, roles, states, live regions, forms, dialogs, dynamic updates, and error communication.
- Contrast, zoom/reflow, text spacing, focus appearance, non-text content, magnification, and visual evidence.

**6C — Hearing, multimedia, and cognitive accessibility**

- Caption, transcript, audio-description, synchronization, and media-control evaluation.
- Predictability, instructions, error prevention/recovery, timing, accessible authentication, consistent help, reading/cognitive load, and structured human review.

**6D — Alternative input, mobile, document, and native profiles**

- Switch, speech/voice, touch, pointer, gesture, and target-size profiles.
- Mobile web and native mobile platform testing.
- PDF/document evaluation with applicable document standards.
- Native desktop accessibility APIs and platform conventions.

**6E — Comprehensive compliance and enterprise workflows**

- Selectable WCAG, GIGW, BIS, EN 301 549, Section 508, and other supported reporting profiles.
- Qualified manual/AT review assignments and sign-off.
- Evidence packages, audit history, procurement exports, organizational dashboards, and API/SDK integrations.
- Continuous monitoring of standard editions, rule mappings, model/browser drift, and historical-report integrity.

---

## 29. First 30–40% presentation milestone

The first major presentation should demonstrate a reliable vertical slice rather than broad but opaque AI behavior.

### Required demonstration

1. A deployed API accepts a team-owned fixture URL and task goal.
2. The run is durably queued and processed by a separate worker.
3. The worker launches an isolated Chromium context.
4. A deterministic keyboard journey runs on an accessible/broken fixture pair.
5. At least KBD-001 through KBD-004 are implemented or represented by working fixture examples.
6. One seeded blocker is correctly detected and its accessible twin passes.
7. The report shows focus/state evidence, screenshot, trace, rule version, and reproduction steps.
8. A pinned axe scan runs at the same relevant states and remains a separate baseline.
9. Restarting the API does not lose the run.
10. The presentation clearly states what has and has not been proven.

### Optional demonstration

Add the AI planner only if the deterministic kernel and durable platform are stable. A reliable scripted journey is a stronger engineering milestone than an unexplained sequence of model actions.

---

## 30. Team structure and ownership

### Member A — Evaluation engine owner

- Observer and state diffing.
- Keyboard executor.
- Detector rules.
- Controlled fixtures.
- Planner integration.
- Evaluation protocol and metrics.

### Member B — Platform owner

- Django application, DRF interface, admin, and OpenAPI contract.
- PostgreSQL models and Django migrations.
- Queue and worker lifecycle.
- Browser isolation and network policy.
- Object storage.
- Deployment and observability.

### Member C — Product and reporting owner

- Django Templates, HTMX interactions, Tailwind styles, and minimal browser scripting.
- Accessible interaction and progress experience.
- Report model and presentation.
- Rerun comparison.
- Remediation references.
- Presentation and report assembly.

### Shared responsibilities

- Architecture and threat-model review.
- Manual ground-truth evaluation.
- Code review.
- Documentation updates.
- Security-sensitive decisions.
- Demo rehearsal and final defense.

No member should be the only reviewer of their own ground-truth labels or security-critical change.

---

## 31. Working process

### Planning

- Work in short weekly iterations.
- Each issue must state user value, acceptance criteria, tests, and owning phase.
- Features outside the current scope go to a future-roadmap backlog.
- Update this master plan when scope or domain language changes.

### Branching and review

- Use short-lived feature branches.
- Require review before merging.
- Keep changes small enough to verify.
- Do not merge failing CI.
- Require additional review for URL policy, authorization, data handling, planner policy, and worker isolation.

#### Mandatory safety-review matrix — resolves TP-003

No author may self-approve a safety-critical change. The required second reviewer is assigned by role before merge:

| Change area | Primary owner | Required independent reviewer | Required evidence |
|---|---|---|---|
| Planner prompt, structured output, and policy validator | Member A / AI-ML | Member B / Platform | rejected-action and prompt-injection tests |
| URL policy, DNS/IP checks, request routing, and public-target allowlist | Member B / Platform | Member C / Product-reporting | SSRF, redirect, method-blocking tests |
| Browser isolation, cancellation, worker cleanup, and secret resolution | Member B / Platform | Member A / AI-ML | cleanup and secret-redaction tests |
| Controlled fixture barrier and ground-truth labels | Member A / Engine or Member C / Fixture | the other of Member A/Member C | independent manual keyboard record |
| Report wording, artifact access, and evidence redaction | Member C / Product-reporting | Member B / Platform | authorization and redaction tests |

The pull request must identify the primary owner, reviewer, tests, and any exception. If only one contributor is available, the change remains unmerged or is limited to non-safety-critical scaffolding until review is possible.

### Definition of done for a feature

A feature is done only when:

- acceptance criteria are met;
- unit/integration tests pass;
- failure and edge cases are covered;
- security/privacy effects are reviewed;
- telemetry is present where required;
- user-facing behavior is keyboard tested;
- schemas/docs are updated; and
- no temporary secret, sensitive fixture data, or unbounded debug logging remains.

### Decision records

Create an Architecture Decision Record only when a decision is:

1. costly to reverse;
2. surprising without context; and
3. a real trade-off between credible alternatives.

Likely ADRs include worker isolation, durable queue choice, evidence storage, target authorization, and authentication approach.

---

## 32. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Team tries to implement every accessibility profile simultaneously | Project becomes unfinishable | Preserve full scope in the roadmap but enforce sequential profile exit gates |
| LLM hallucinates or loops | False results, cost, latency | Typed actions, policy validation, state-based loop detection, budgets |
| LLM incorrectly declares success | Unsafe false completion | Explicit completion signals and deterministic goal oracle |
| Legitimate modal containment is labeled a trap | False positive | Pattern-aware rules, exit tests, negative controls |
| Public URL enables SSRF or internal access | Critical platform compromise | Allowlist, DNS/IP/redirect checks, egress proxy, isolation |
| Target page prompt-injects the planner | Policy bypass or data leak | Treat page as untrusted, least privilege, post-model authorization |
| Journey performs an unapproved real-world action | Harm to users/site owner | Execution modes, sandbox adapters, human approval, synthetic data, expected-effect and cleanup assertions |
| Evidence contains personal data | Privacy/legal harm | Minimization, redaction, short retention, access control, deletion |
| API restart loses runs | Reliability failure | Durable queue and transactional run creation |
| Local artifacts disappear or block scaling | Data loss | S3-compatible object storage |
| Model/SDK is deprecated | Service interruption | Provider adapter, supported model configuration, regression gate |
| Real sites change during evaluation | Irreproducible results | Controlled benchmark plus dated authorized sample |
| Axe and journey counts are compared incorrectly | Invalid academic conclusion | Matched states and adjudicated barrier identity |
| Team spends too long on infrastructure | Course delay | Modular monolith, managed services, phase exit gates |
| Demo depends on live third-party availability | Presentation failure | Primary demo uses local/team-owned versioned fixtures |

---

## 33. Assumptions and pending decisions

### Approved baseline assumptions

- Current phase is motor-disability/keyboard-only.
- Chromium is the first and only required browser.
- The full product includes complete journeys and multiple future accessibility profiles; keyboard motor accessibility is implemented first.
- The system supports compliance traceability and qualified evaluation, but automated journey results alone are not certification.
- AI is a bounded planner, not the compliance oracle.
- Deterministic evidence is implemented before AI navigation.
- The deployed MVP tests allowlisted or owner-authorized targets.
- Observe-only mode stops before side effects; sandbox-transactional mode completes authorized test actions and verifies cleanup.
- The platform uses separate API and worker processes.
- Metadata uses PostgreSQL and artifacts use object storage.
- The benchmark includes controlled accessible/broken fixtures.
- No stealth or anti-bot bypass is used.

### Decisions to confirm during Phase 0

1. Exact hosted OIDC provider.
2. Exact object-storage provider.
3. Initial container hosting platform and budget.
4. Managed Redis provider.
5. Current supported Gemini model identifier and quota.
6. Final evidence-retention period.
7. Exact real-world targets with written authorization.
8. Open-source license and publication plan.
9. Whether printable PDF export is required for the course submission.
10. Course dates mapped onto the relative phase schedule.
11. Which account, booking, commerce/payment, messaging, upload, and destructive-action fixtures are mandatory for the final keyboard-track evaluation.
12. Which compliance profiles are enabled for the first release and who owns their criterion-level review.

These decisions must not change the logical boundaries described in this document without review.

---

## 34. Presentation-ready project summary

### 30-second explanation

> AccessPath AI is a goal-driven accessibility evaluation platform for complete digital journeys. It begins with motor accessibility: a developer provides an approved website or sandbox and a task such as registering an account, booking an appointment, completing a test checkout, or submitting a form. The system attempts the journey using only keyboard actions, records each focus and state transition, and reports whether the task completed, where a reproducible barrier blocked it, or why the result was inconclusive. The same evidence and compliance architecture is designed to add screen-reader, visual, hearing, cognitive, mobile, document, and native accessibility profiles later.

### Problem slide

- Automated scans identify many page-level issues.
- They do not by themselves prove that a keyboard user can complete a multi-step task.
- Developers need task impact, blocker location, and evidence.

### Solution slide

- Plain-language task goal.
- Real browser.
- Strict keyboard-only action policy.
- Bounded AI planning.
- Deterministic state and rule evaluation.
- Evidence-backed report and rerun comparison.

### Technical contribution slide

- Hybrid AI/deterministic architecture.
- Versioned keyboard rules.
- Extensible accessibility and compliance profile registry.
- Safe full-workflow execution modes for authentication and state-changing sandbox journeys.
- Durable isolated browser execution.
- Controlled benchmark and manual ground truth.
- Fair per-state comparison with axe-core.

### Scope slide

**Full project:** complete functional journeys; motor, visual, hearing, cognitive, mobile, document, and native accessibility profiles; comprehensive standards traceability.  
**Current implementation:** motor accessibility through keyboard-only desktop Chromium journeys, including authorized authenticated and sandbox-transactional flows.  
**Later profiles:** screen readers, visual/low-vision, multimedia/hearing, cognitive, alternative input, mobile, PDF/document, native, and broader compliance exports.  
**Permanent boundaries:** no unauthorized testing, bypassing controls, uncontrolled real-world effects, or unsupported certification claims.

### Evaluation slide

- Controlled accessible/broken fixtures.
- Authorized real-world journeys.
- Two independent manual reviewers.
- Precision, recall, false completion, false block, consistency, latency, and cost.

### Responsible-use slide

- Domain authorization.
- SSRF and egress protection.
- Isolated disposable workers.
- Prompt-injection defense.
- Synthetic data and safety stop.
- Evidence minimization and retention.

---

## 35. Suggested academic report structure

1. Abstract.
2. Introduction and motivation.
3. Background: web accessibility, keyboard interaction, WCAG, automated testing.
4. Problem definition and research question.
5. Related tools and limitations of existing approaches.
6. Project scope and ethical/safety boundaries.
7. System requirements.
8. Architecture and technology choices.
9. Keyboard evaluation engine.
10. AI planner and policy controls.
11. Detector-rule design.
12. Security and privacy design.
13. Benchmark and evaluation methodology.
14. Implementation.
15. Results.
16. Error analysis and limitations.
17. Discussion and future work.
18. Conclusion.
19. References.
20. Appendices: schemas, rule definitions, fixture catalogue, and raw metrics.

---

## 36. Definition of final project success

### 36.1 Keyboard-first course success

The keyboard-first course delivery is successful when:

- the declared MVP scope is implemented without relying on mouse interaction;
- controlled examples cover public, authenticated, booking, payment-sandbox, form, messaging/upload, and account-management journeys;
- deterministic evidence supports every verified finding;
- the AI planner remains bounded by typed actions and policy;
- the system survives API restart and handles worker failure explicitly;
- target and user isolation controls pass the security test suite;
- the report distinguishes completion, verified blocking, uncertainty, and system failure;
- controlled and authorized real-world evaluation is completed;
- results include both strengths and limitations;
- a tagged release can reproduce the benchmark; and
- the team can defend the contribution without claiming whole-site accessibility or unsupported market uniqueness.

### 36.2 Full project-vision success

The broader AccessPath AI vision is successful when:

- multiple validated accessibility profiles can evaluate the same complete journeys without replacing the core platform;
- visual, screen-reader, hearing/multimedia, cognitive, alternative-input, mobile, document, and native coverage is represented by implemented or qualified manual/AT protocols;
- every enabled compliance profile has criterion-level applicability, coverage state, evidence, limitations, and edition traceability;
- authenticated and state-changing workflows run safely through environment-specific authorization, sandbox integrations, secret isolation, approval, and cleanup;
- automated, semi-automated, manual, and user-evaluation results are presented together without overstating certainty;
- regression, CI, monitoring, team review, and procurement/reporting workflows can operate at scale; and
- historical reports remain reproducible and interpretable as standards, browsers, models, rules, and assistive technologies evolve.

---

## 37. Immediate next steps

The team should not begin with the complete autonomous agent. Begin in this order:

1. Approve or edit this master plan as a team.
2. Assign the three ownership areas.
3. Map the relative schedule to course dates.
4. Create the repository structure and CI skeleton.
5. Seed the compliance register with WCAG 2.2 and mark each criterion's current coverage state.
6. Write the threat model, data-flow diagram, execution modes, target/action/side-effect policies, and cleanup contract.
7. Define the controlled fixture roadmap for registration/authentication, booking, payment-sandbox checkout, forms, messaging, uploads, consent, and account management.
8. Build the first accessible/broken controlled fixture pair.
9. Implement deterministic observation and keyboard execution.
10. Implement KBD-001 through KBD-004 and evidence capture.
11. Add the durable API/queue/worker/storage path.
12. Add the AI planner only after the deterministic vertical slice is stable.
13. Expand the keyboard benchmark to full controlled journeys before beginning later accessibility profiles.

---

## 38. Primary references

### Accessibility

- [W3C Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C: What is new in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/)
- [WAI-ARIA Authoring Practices: Developing a Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
- [WAI-ARIA 1.2](https://www.w3.org/TR/wai-aria-1.2/)
- [W3C Accessibility Conformance Testing overview](https://www.w3.org/WAI/standards-guidelines/act/)
- [W3C ACT Rules Format 1.1](https://www.w3.org/TR/act-rules-format/)
- [W3C WCAG Evaluation Methodology 2.0](https://www.w3.org/TR/WCAG-EM/)

### India

- [Rights of Persons with Disabilities Act, 2016](https://www.indiacode.nic.in/bitstream/123456789/13684/1/a2016-49_act.pdf)
- [Guidelines for Indian Government Websites 3.0](https://guidelines.india.gov.in/)
- [Digital Personal Data Protection Act, 2023](https://www.indiacode.nic.in/indiacode/handle/123456789/22037?view_type=browse)
- [Digital Personal Data Protection Rules, 2025](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025)
- [Department of Empowerment of Persons with Disabilities: notified standards and rules](https://depwd.gov.in/en/document-category/rules-regulations/)

### International and procurement profiles

- [ETSI Human Factors accessibility standards](https://www.etsi.org/technical-groups/hf/)
- [European Accessibility Act — Directive (EU) 2019/882](https://eur-lex.europa.eu/eli/dir/2019/882/oj)
- [US Access Board: Revised Section 508 Standards](https://www.access-board.gov/ict/)

### Security and AI governance

- [OWASP Application Security Verification Standard](https://owasp.org/projects/asvs)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP GenAI Security Project](https://genai.owasp.org/llm-top-10/)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)

### Technology

- [Django supported versions and release roadmap](https://www.djangoproject.com/download/)
- [Django 5.2 documentation](https://docs.djangoproject.com/en/5.2/)
- [Django asynchronous support](https://docs.djangoproject.com/en/5.2/topics/async/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [drf-spectacular OpenAPI generation](https://drf-spectacular.readthedocs.io/)
- [HTMX documentation](https://htmx.org/docs/)
- [Celery stable documentation](https://docs.celeryq.dev/en/stable/)
- [PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/)
- [Uvicorn documentation](https://www.uvicorn.org/)
- [uv project and dependency management](https://docs.astral.sh/uv/)
- [Ruff documentation](https://docs.astral.sh/ruff/)
- [Pyright documentation](https://microsoft.github.io/pyright/)
- [Playwright Python documentation](https://playwright.dev/python/)
- [Playwright Docker security guidance](https://playwright.dev/python/docs/docker)
- [Google Gemini API libraries](https://ai.google.dev/gemini-api/docs/libraries)
- [Google Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Render background workers](https://render.com/docs/background-workers)
- [Render persistent disks](https://render.com/docs/disks)
- [OpenTelemetry documentation](https://opentelemetry.io/docs/)

---

## 39. Change log

| Version | Date | Summary |
|---|---|---|
| 2.3 | 26 September 2026 | Added deterministic completion, planner-observation, policy-rejection, state-progress, and loop contracts; outbox crash recovery; verified version pins; independent safety-review assignments; evaluation freeze/staffing rules; and a literature-positioning protocol that narrows the academic claim to task-level evidence-backed localization |
| 2.2 | 25 September 2026 | Approved a strict Python-first architecture: Django 5.2 LTS modular monolith with Templates/HTMX, DRF/OpenAPI, PostgreSQL 18, Celery 5.6/Redis, isolated async Playwright workers, S3-compatible evidence storage, and one Python quality toolchain; replaced the earlier split React/FastAPI plan and documented stable module seams, repository structure, testing, phases, ownership, and rejected alternatives |
| 2.1 | 24 September 2026 | Clarified keyboard accessibility as the first implementation track rather than the permanent boundary; added complete authenticated and transactional journeys, execution modes, cleanup, comprehensive compliance coverage states, later accessibility profiles, and full-project success criteria |
| 2.0 | 24 September 2026 | Consolidated project concept, readiness review, standards research, domain glossary, architecture, implementation plan, and presentation/report guidance into one canonical document |
