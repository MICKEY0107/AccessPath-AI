# AccessPath AI: industrial keyboard-automation product direction

**Research date:** 11 October 2026  
**Decision horizon:** current keyboard evaluator first; VS Code and voice-assisted browser surfaces second  
**Status:** product and implementation recommendation; not a WCAG conformance claim or legal advice

## Executive decision

The next goal should be:

> Given an authorized website, a declared user journey, and a versioned keyboard-only interaction profile, AccessPath AI should reproducibly determine whether the journey can be completed using real keyboard events, identify and reproduce keyboard barriers, and produce auditable evidence without performing an unapproved side effect.

This goal is narrower and more defensible than “automatically test accessibility on any site.” It is also the reusable core for both later ideas:

- A VS Code extension can present findings from this engine while a developer is working.
- A voice-driven Chrome extension can reuse the intent, action, and policy contracts, but it is a separate assistive product with materially higher privacy and safety requirements.

The priority order should therefore be:

1. Harden the current engine into an authorized real-site **keyboard journey evaluator**.
2. Add a thin **developer workflow** through CLI/CI and then VS Code.
3. Run a separate, user-researched **voice browser assistant** discovery track; do not make it the next implementation milestone.

## Why this is the right product boundary

WCAG 2.2 provides the normative baseline for the current scope: functionality must be keyboard-operable, focus must not become trapped, sequential focus order must preserve meaning and operability, focus must be visible, and focused components must not be entirely hidden by author-created content ([WCAG 2.2: 2.1.1 Keyboard](https://www.w3.org/TR/WCAG22/#keyboard), [2.1.2 No Keyboard Trap](https://www.w3.org/TR/WCAG22/#no-keyboard-trap), [2.4.3 Focus Order](https://www.w3.org/TR/WCAG22/#focus-order), [2.4.7 Focus Visible](https://www.w3.org/TR/WCAG22/#focus-visible), [2.4.11 Focus Not Obscured](https://www.w3.org/TR/WCAG22/#focus-not-obscured-minimum)). Character-only shortcuts also have specific disable, remap, or focus constraints ([WCAG 2.2: 2.1.4 Character Key Shortcuts](https://www.w3.org/TR/WCAG22/#character-key-shortcuts)).

A journey-level product is important because WCAG conformance applies to complete pages and complete processes, not merely to a few selected controls ([Understanding WCAG conformance](https://www.w3.org/WAI/WCAG22/Understanding/conformance)). WCAG-EM likewise says a representative evaluation includes all views in a complete process and structures evaluation around scope, product exploration, representative sampling, evaluation, and reporting ([WCAG-EM 2.0](https://www.w3.org/TR/WCAG-EM/), [WCAG-EM overview](https://www.w3.org/WAI/test-evaluate/conformance/wcag-em/)).

The product must not claim automatic WCAG certification. W3C warns that evaluation tools cannot test every accessibility aspect and that human judgment is required ([Selecting Web Accessibility Evaluation Tools](https://www.w3.org/WAI/test-evaluate/tools/selecting/)). ACT rules make testing more transparent across automated, semi-automated, and manual procedures, but the published rules are informative rather than independent conformance determinations ([ACT overview](https://www.w3.org/WAI/standards-guidelines/act/), [ACT rules](https://www.w3.org/WAI/standards-guidelines/act/rules/)).

The user need is valid and broader than conventional keyboard users. W3C describes people with physical disabilities using specialized keyboards, switches, speech recognition, eye tracking, and other hands-free interaction, and notes that speech input can use the keyboard interface underneath ([WAI: Physical abilities and barriers](https://www.w3.org/WAI/people-use-web/abilities-barriers/physical/), [Understanding Guideline 2.1](https://www.w3.org/WAI/WCAG21/Understanding/keyboard-accessible)). That makes the current keyboard engine a useful technical base for later assistive input, while not proving that the future voice product is usable or safe.

## What exists in this repository

The current implementation already has the right prototype seams:

- versioned Pydantic contracts for observations, actions, policy decisions, action results, and step evidence (`engine/contracts.py`);
- a small real-keyboard action vocabulary and Playwright executor (`engine/executor.py`);
- deterministic authorization before execution (`engine/policy.py`);
- origin checks, action budgets, state fingerprints, completion signals, screenshots, and persisted run steps;
- explicit planner-provider metadata and a deterministic contingency path;
- a controlled accessible journey and a paired known keyboard barrier;
- Django, Celery, PostgreSQL, and artifact abstractions suitable for further hardening.

The most important current limitations are:

- the barrier oracle is fixture-specific (`data-testid` plus an action budget), not a general detector catalogue;
- page observation is a custom DOM summary, not a frame-aware accessibility representation;
- the current selector misses many composite-widget semantics and cannot model `aria-activedescendant` behavior;
- state change is broad and does not prove that an intended control was activated correctly;
- only the final completion policy is deterministic; intermediate journey assertions are absent;
- a page is created directly rather than through an explicitly configured, isolated browser context with network interception;
- redirect, popup, download, dialog, request-method, service-worker, DNS/IP, and egress policies are not production-grade;
- artifacts are local and do not yet have redaction, retention, access control, or durable object storage;
- job recovery, idempotency, leases, cancellation, and dead-letter behavior remain planned rather than proven;
- the corpus is one journey family, so accuracy and repeated-run agreement on representative real applications are unknown.

These gaps mean the next milestone is **engine trustworthiness**, not a new user interface.

## Product scope for the first industrial release

### In scope

- Explicitly authorized customer-owned staging sites.
- Public accessibility demonstration sites in read-only mode.
- Customer-owned production sites in read-only mode only after staging validation.
- Declared end-to-end journeys such as sign-in with a disposable test account, search, form completion without submission, booking sandbox, and account recovery sandbox.
- Real keyboard events: `Tab`, `Shift+Tab`, arrows, `Home`, `End`, `Enter`, `Space`, `Escape`, and bounded text entry.
- Component-aware keyboard expectations for native controls and supported ARIA patterns.
- Findings with reproduction keys, focus history, state evidence, screenshots, accessibility snapshots, and rule/version metadata.
- Outcomes that distinguish journey completion, keyboard failure, needs-review, inconclusive, safety stop, planner failure, and system failure.
- axe-core scans at meaningful UI states as a separate semantic signal.

### Explicitly out of scope

- “Test any URL” or unrestricted crawling.
- Automatic WCAG certification or a legal-compliance verdict.
- Real purchases, bookings, messages, file uploads, account changes, or personal-data entry.
- CAPTCHA, bot-defense, authentication, or access-control bypass.
- Screen-reader equivalence or claims about complete assistive-technology support.
- Visual, cognitive, multimedia, mobile-native, PDF, or desktop accessibility profiles in this release.
- Autonomous remediation of a customer’s source code.

### Meaning of “actual site”

For the next release, an actual site should mean an **authorized staging application with production-representative markup and workflows**, not a random public production site. The progression should be:

1. controlled fixtures and component laboratories;
2. customer-owned staging with disposable accounts and synthetic data;
3. approved public demo pages in read-only mode;
4. production read-only smoke journeys;
5. transactional production testing only if a later product has explicit authorization, typed integrations, human approval, and verified cleanup.

## Required testing model

### 1. Journey contract

Each test should be an immutable, versioned contract rather than only a natural-language prompt. A `JourneySpec` should include:

- goal and user profile;
- start state and authentication reference;
- allowed origins and path prefixes;
- setup and cleanup hooks;
- synthetic permitted inputs by semantic field name;
- checkpoints and deterministic assertions for intermediate states;
- final completion oracle;
- permitted side-effect class;
- expected dialogs, downloads, popups, and new tabs;
- action, time, page, retry, and model-cost budgets;
- browser/viewport/locale/time-zone profile;
- artifact and redaction policy.

Natural language should help the planner choose among allowed actions; it must not define authorization, safety, or success.

### 2. Target authorization manifest

Every external target should have a reviewed `TargetManifest` with owner, authorization evidence, environment class, exact URL boundaries, approved HTTP methods, allowed resource origins, data classification, retention period, prohibited controls, and review expiry. Unknown redirects, popups, downloads, methods, and origins should fail closed.

Playwright supports isolated, non-persistent browser contexts that do not write browsing data to disk, context-level request routing, and HAR replay; its documentation recommends blocking service workers when request interception must be dependable ([Playwright `BrowserContext`](https://playwright.dev/python/docs/api/class-browsercontext), [Playwright service workers](https://playwright.dev/python/docs/service-workers)). Use those controls inside the worker, and enforce DNS/IP and outbound-network restrictions outside the browser as a second boundary.

### 3. Deterministic interaction and evidence layer

The engine should always record:

- key down/up sequence and timing;
- URL, frame path, focused element, accessible role/name/state, and bounding box before and after;
- focus-indicator evidence and viewport occlusion evidence;
- `aria-activedescendant` and selected/expanded/checked state where applicable;
- page, form, and application-state fingerprint;
- console errors, page errors, dialogs, downloads, popup creation, and network-policy events;
- rule evaluation with applicability, outcome, confidence/review status, and WCAG/APG mapping;
- engine, policy, browser, OS image, model, prompt, target, and journey versions.

Playwright can capture ARIA snapshots, including role/name structure, and can include element references and bounding boxes in AI-oriented snapshots ([Playwright Python `aria_snapshot`](https://playwright.dev/python/docs/api/class-locator#locator-aria-snapshot)). Its traces include browser operations, DOM snapshots, screenshots, and network activity, so traces are valuable evidence but must be protected and retained deliberately ([Playwright Trace Viewer](https://playwright.dev/docs/trace-viewer)).

### 4. Component-aware action model

A Tab-only crawler is insufficient. APG explains that `Tab` and `Shift+Tab` conventionally move between components, while arrows and other keys move inside composite widgets such as radio groups, tab lists, menus, listboxes, trees, and grids ([APG keyboard interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)). ARIA semantics do not create behavior by themselves; custom widgets require authors to implement the expected interaction ([APG Read Me First](https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/)).

Build versioned interaction adapters for at least:

- native links, buttons, inputs, selects, text areas, checkboxes, and radio groups;
- dialogs and focus restoration;
- tabs;
- menus and menubars;
- comboboxes/listboxes;
- disclosure controls;
- grids and trees only after the simpler patterns are stable.

APG examples are informative patterns, not a replacement for WCAG or a production-ready component library ([APG introduction](https://www.w3.org/WAI/ARIA/apg/about/introduction/)). The engine should therefore report “matches the tested interaction expectation,” not “ARIA compliant.”

### 5. Detector catalogue

Implement each detector as a versioned rule with applicability, procedure, evidence, outcome, limitations, and gold test cases. Start with:

1. reachable by sequential keyboard navigation;
2. operable by the expected activation key;
3. no keyboard trap or unintended focus loop;
4. focus order review;
5. visible focus;
6. focus not fully obscured;
7. dialog initial focus, containment, Escape behavior, and restoration;
8. composite-widget navigation;
9. focus preservation after DOM updates, validation, and route changes;
10. character-key shortcut review.

Use four rule results: `passed`, `failed`, `needs_review`, and `not_applicable`. Focus-order meaning, some trap cases, and similar judgment-heavy checks must be reviewable rather than forced into a false binary. W3C’s Easy Checks provides a practical manual comparison procedure covering reachability, escape, logical order, visible focus, and complete keyboard functionality ([WAI Easy Checks: keyboard](https://www.w3.org/WAI/test-evaluate/preliminary/#keyboard)).

### 6. Planner as an optional navigation strategy

Keep three separable modes:

- **deterministic replay:** executes a reviewed key sequence and assertions;
- **bounded exploration:** discovers a likely keyboard path without side effects;
- **goal-driven planner:** chooses the next permitted action from a sanitized observation.

All three modes must use the same policy, executor, detectors, evidence schema, and completion oracle. A model failure must not become an accessibility failure. Page text is untrusted data and must never change the goal, policy, tool permissions, or success criteria.

### 7. axe-core as a companion, not the engine

axe-core can run WCAG-related rules in the rendered page and returns uncertain items as `incomplete`; its project states that it finds about 57% of WCAG issues automatically ([axe-core official repository](https://github.com/dequelabs/axe-core)). Its API also notes that inactive or hidden regions must be exposed and scanned again ([axe-core API](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md)). Run it at named journey checkpoints and preserve its results separately from keyboard-interaction findings.

## Proposed architecture

```text
CLI / CI / Web UI / future VS Code adapter
                    |
               Run API
                    |
       durable orchestrator + outbox
                    |
          isolated browser worker
                    |
   +----------------+----------------+
   |                |                |
Target policy   Journey oracle   Planner adapter
   |                |                |
Network gate    Rule engine      deterministic / AI
   +----------------+----------------+
                    |
          keyboard-only executor
                    |
    focus + accessibility + state observer
                    |
      immutable evidence and rule results
                    |
       object storage + report + review
```

Important design rules:

- The executor accepts typed actions, never generated scripts or selectors.
- The planner sees only bounded, sanitized observations and synthetic permitted inputs.
- Credentials are opaque references resolved inside the worker and never enter planner context.
- The worker uses an explicit isolated context per run.
- Network policy is context-wide so popups and subframes are covered.
- Browser automation remains based on Playwright; CDP-only features are optional because CDP sessions are Chromium-specific ([Playwright `newCDPSession`](https://playwright.dev/docs/api/class-browsercontext#browser-context-new-cdp-session)).
- Open shadow DOM and frames receive explicit coverage; closed shadow roots are disclosed as a limitation because Playwright’s normal locators do not pierce them ([Playwright shadow DOM locators](https://playwright.dev/docs/locators#locate-in-shadow-dom), [Playwright `FrameLocator`](https://playwright.dev/docs/api/class-framelocator)).
- Browser projects cover Chromium first, then Firefox and WebKit; Playwright supports those engines as separate browser targets ([Playwright browsers](https://playwright.dev/docs/browsers)).

## Proposed release gates

These are product targets, not thresholds defined by WCAG.

### Safety gate

- 100% of adversarial tests block unapproved origins, methods, redirects, popups, downloads, and side-effect controls.
- Observe-only runs produce zero application-side mutations in the test oracle.
- No credential, token, real personal data, or protected form value appears in planner requests, ordinary logs, reports, screenshots after redaction, or downloadable traces.
- Every run has hard action, time, page, retry, origin, and cost limits.
- Cancellation and timeout leave no browser child process or temporary artifact behind.

### Correctness gate

- Zero false `completed` outcomes across the versioned negative-control corpus.
- Every `completed` outcome satisfies deterministic checkpoint and completion assertions.
- Every `failed` keyboard finding includes a replayable minimal key sequence and evidence.
- Each supported detector has accessible, broken, ambiguous, and not-applicable gold cases.
- For a frozen pilot corpus, target at least 95% precision and 90% recall per supported detector; detectors below the threshold remain `experimental` or are re-scoped.
- Judgment-heavy rules expose `needs_review`; unsupported rules are never reported as passed.

### Reliability gate

- Five consecutive successful runs for each deterministic accessible journey on each supported browser profile.
- At least 95% repeated-run agreement on the frozen pilot corpus.
- Restart, duplicate delivery, browser crash, planner timeout, storage failure, and broker failure produce a recovered run or an explicit terminal system outcome without duplicate side effects.
- Artifacts survive worker and web-service restarts and remain access-controlled.
- A fixed, versioned environment can replay a recorded run and reproduce its rule outcomes.

### Coverage gate

- At least 30 gold journeys across native controls, dialogs, tabs, menus, combobox/listbox behavior, validation recovery, SPA route changes, and focus restoration.
- At least four realistic workflow families, including one authenticated disposable-account journey and one sandbox transaction.
- At least two authorized partner staging applications in addition to the controlled corpus.
- Chromium is required for the first pilot; Firefox and WebKit are added before claiming cross-browser support.

### Reporting gate

- Reports clearly separate journey outcome, keyboard findings, axe results, safety events, model/runtime failures, and manual-review items.
- Reports identify exact target retrieval time/version, journey version, browser profile, rule versions, and limitations.
- The interface never translates a keyboard-profile result into “WCAG compliant.”

## Implementation plan

### Phase 0 — freeze the contract and benchmark (1–2 weeks)

1. Write the product claim, non-claims, outcome taxonomy, and target authorization policy.
2. Define `TargetManifest.v2`, `JourneySpec.v2`, `RuleResult.v1`, and an extended evidence contract.
3. Turn the existing accessible/broken clinic into the first gold corpus.
4. Add component fixtures for focus loops, legitimate modal containment, focus loss, focus restoration, visible/obscured focus, tabs, menus, and comboboxes.
5. Establish human-reviewed expected outcomes and a benchmark runner.

**Exit:** every supported result is defined by a deterministic rule or explicitly marked for review.

### Phase 1 — harden browser execution and safety (2–3 weeks)

1. Create one explicit non-persistent browser context per run.
2. Add context-level request interception, service-worker blocking where required, method/origin/path policy, redirect validation, popup/dialog/download controls, and external egress enforcement.
3. Make observation frame-aware and accessibility-aware; record `aria-activedescendant`, geometry, occlusion, scroll, and focus-indicator evidence.
4. Replace fixed waits with event/condition-based stabilization plus bounded fallback timing.
5. Add trace capture on failure or retry, redaction, retention, and durable artifact storage.
6. Implement worker leases, heartbeats, idempotency, cancellation, and crash recovery.

**Exit:** the safety and recovery suites pass without network or side-effect escape.

### Phase 2 — build the keyboard rule engine (2–4 weeks)

1. Implement detector rules in the order listed above.
2. Add component-aware key maps and expected-state transitions.
3. Separate `no_effect`, `wrong_effect`, `focus_lost`, `loop`, `unreachable`, and `needs_review` outcomes.
4. Add axe-core at journey checkpoints without merging its verdicts into keyboard findings.
5. Add deterministic replay and compare evidence across reruns.
6. Measure precision, recall, false completion, false block, inconclusive rate, and agreement against the gold corpus.

**Exit:** supported detectors meet their declared benchmark gate or remain labeled experimental.

### Phase 3 — authorized real-site pilot (3–5 weeks)

1. Onboard two customer-owned staging applications through reviewed manifests.
2. Begin with navigation and form completion without submission.
3. Add disposable authentication and a sandbox transaction only after secrets and cleanup controls pass.
4. Run Chromium first, then add Firefox and WebKit profiles.
5. Have accessibility reviewers adjudicate false positives, false negatives, and ambiguous outcomes.
6. Include users with motor disabilities in task selection and usability review; WCAG-EM recommends involving people with disabilities to address real-life experience ([WCAG-EM overview](https://www.w3.org/WAI/test-evaluate/conformance/wcag-em/)).

**Exit:** pilot metrics, limitations, and failure cases are retained, not only successful demos.

### Phase 4 — developer delivery surface (2–3 weeks)

1. Stabilize a local CLI and CI-friendly JSON/SARIF-style report contract.
2. Add a run API, progress stream, baseline comparison, and links from findings to replay evidence.
3. Build a thin VS Code extension that starts or watches a local preview, launches a selected journey, and renders diagnostics plus explicit code actions.
4. Keep static source lint and rendered-browser findings visually distinct.

VS Code supports diagnostics, hovers, CodeLens, and code actions through its language-feature APIs, or through a reusable language server ([VS Code programmatic language features](https://code.visualstudio.com/api/language-extensions/programmatic-language-features), [VS Code language server guide](https://code.visualstudio.com/api/language-extensions/language-server-extension-guide)). If the extension runs project code or consumes workspace-controlled executable configuration, it must integrate with Workspace Trust and Restricted Mode ([VS Code Workspace Trust guide](https://code.visualstudio.com/api/extension-guides/workspace-trust)). Any telemetry must honor the editor’s telemetry setting and avoid PII ([VS Code telemetry guide](https://code.visualstudio.com/api/extension-guides/telemetry)).

**Exit:** a developer can reproduce a finding from the editor without the extension owning a second evaluation engine.

## Decision on the two parallel ideas

| Idea | Value | Reuse from current work | Main new risk | Recommendation |
|---|---|---|---|---|
| VS Code live assistant | Moves detection earlier and shortens fix/retest cycles | Rule IDs, journey runner, reports, replay, API | Framework/source mapping, workspace execution, noisy feedback | Build second, as a thin adapter after the engine contract is stable |
| Voice-driven Chrome extension | Directly assists users with hands-free task completion | Intent/action schema, semantic observation, policy concepts | Real user identity, sensitive page content, microphone data, irreversible actions, unpredictable sites | Run discovery now; implement only after the evaluator is safe and after research with motor-disabled users |

### What the VS Code product should actually do

The first editor release should not continuously send source code to a model or pretend static analysis can prove keyboard behavior. It should:

- flag deterministic source-level issues when a linter can do so;
- start a rendered keyboard journey against the developer’s local preview;
- stream concise progress without stealing focus;
- place diagnostics on mapped source locations when mapping is reliable;
- offer a “reproduce in browser” action and evidence link;
- suggest remediations, but require the developer to apply and review changes;
- rerun the affected journey and compare the result to the baseline.

This keeps one source of truth: the browser rule engine.

### What must be proved before building the voice extension

The voice extension is not simply a new planner UI. It acts inside the user’s authenticated browser and may encounter health, financial, communication, or account data. Before implementation, validate with target users:

- how they invoke, pause, cancel, and recover from recognition errors;
- which actions can run immediately and which need read-back plus confirmation;
- how focus, progress, and errors are announced without requiring precise pointer use;
- acceptable latency and offline behavior;
- whether speech, transcripts, page content, and action history may leave the device;
- how the user takes over with keyboard, switch, eye tracking, or another input mode.

If built, use Manifest V3 with packaged code, a user-invoked shortcut/action, `activeTab` rather than persistent `<all_urls>` access where possible, isolated-world content scripts, a persistent run state outside service-worker globals, and explicit confirmation for irreversible actions. Chrome documents that `activeTab` gives temporary access after a user gesture and revokes it on navigation or close ([Chrome `activeTab`](https://developer.chrome.com/docs/extensions/develop/concepts/activeTab)); it requires the narrowest necessary permissions ([Chrome extension permissions](https://developer.chrome.com/docs/extensions/develop/concepts/declare-permissions)). Content scripts are isolated by default but must still treat page input as hostile ([Chrome content scripts](https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts)). Manifest V3 service workers are ephemeral, so state cannot live only in global variables ([Chrome service-worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)), and remotely hosted executable code is disallowed ([Manifest V3 overview](https://developer.chrome.com/docs/extensions/develop/migrate/what-is-mv3)).

The extension must also disclose data collection accurately, obtain informed consent, minimize data to its single purpose, request minimum permissions, transmit data securely, and publish a privacy policy as applicable ([Chrome Web Store program policies](https://developer.chrome.com/docs/webstore/program-policies/policies), [Chrome user privacy guidance](https://developer.chrome.com/docs/extensions/develop/security-privacy/user-privacy)).

## Recommended immediate backlog

Do these next, in order:

1. Adopt the north-star product statement and outcome/non-claim taxonomy.
2. Convert the current journey configuration into versioned target and journey contracts.
3. Build explicit browser-context and network safety boundaries.
4. Add gold fixtures for trap, focus restoration, composite widgets, visible focus, and focus occlusion.
5. Implement deterministic replay and per-rule results before adding more planner sophistication.
6. Add accessibility snapshots, focus geometry, traces-on-failure, and redaction.
7. Add restart-safe orchestration and durable artifact storage.
8. Freeze a pilot benchmark and publish precision, recall, false-completion, agreement, latency, and cost results.
9. Onboard the first authorized staging site.
10. Only then expose the stable runner through CLI/CI and a VS Code prototype.

## One-sentence positioning

**AccessPath AI is an evidence-first keyboard journey evaluator for authorized web applications: it reproduces how a keyboard user moves through a real task, proves completion or pinpoints a blocker, and shows developers exactly what happened without claiming automated accessibility certification.**
