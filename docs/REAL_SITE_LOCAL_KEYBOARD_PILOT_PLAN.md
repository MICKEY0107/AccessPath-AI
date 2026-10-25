# AccessPath AI — focused plan for local testing on a live website

**Plan date:** 11 October 2026  
**Scope:** Complete the current keyboard-testing prototype so it can run locally against one real public website.  
**Deployment:** Not included.  
**Later products:** VS Code and voice-extension work are not included.

## 1. Goal

From the existing local AccessPath AI interface, start a declared journey against an approved live website, allow the planner to choose only typed keyboard actions, execute those actions in a fresh Playwright browser context, and return an evidence-backed outcome without submitting data or leaving the approved target.

The first real-site proof will be:

> Starting from the English Wikipedia Main Page, use keyboard interaction to find and open the “Web accessibility” article.

This is a real, externally hosted, operational website journey. It exercises focus traversal, editable-field detection, typing, activation, navigation, page-state observation, and deterministic completion without logging in or causing a material side effect.

## 2. Definition of done

The milestone is complete only when all of the following are true:

1. A user can select the Wikipedia journey in the local AccessPath AI UI and start it.
2. The run starts in a new anonymous, non-persistent browser context.
3. The executor uses only the existing keyboard-action schema; it does not click, call target JavaScript, or use a CSS selector to perform the journey.
4. The planner can identify the search field from semantic page information, focus it, type `Web accessibility`, activate the search, and reach the article.
5. `completed` is returned only when both conditions remain true for two observations:
   - URL path equals `/wiki/Web_accessibility`.
   - A level-one heading has the accessible name `Web accessibility`.
6. Every attempted action records focus before/after, page state, policy decision, result, timing, and screenshots.
7. The run cannot navigate to an unapproved document origin, use a state-changing HTTP method, open an uncontrolled popup, or trigger a download.
8. Three consecutive live-planner runs complete without deterministic fallback.
9. Five deterministic/replay runs complete consecutively.
10. A failure in the model, network, page layout, or policy is reported as `agent_error`, `environment_blocked`, `safety_stopped`, or `inconclusive`; it is never misreported as an accessibility failure or completion.

## 3. Target policy

### Approved document target

- Start URL: `https://en.wikipedia.org/wiki/Main_Page`
- Allowed navigation origin: `https://en.wikipedia.org`
- Allowed navigation path prefixes: `/wiki/` and the search endpoint required by the current Wikipedia UI
- Expected final URL: `https://en.wikipedia.org/wiki/Web_accessibility`

### Permitted behavior

- Anonymous browsing only.
- One run at a time.
- `GET`, `HEAD`, and required preflight/resource requests only.
- Keyboard focus traversal, bounded text entry, and activation.
- Normal static resources from explicitly reviewed Wikimedia resource origins.
- Maximum 40 executed actions and five minutes per run.
- Screenshots and local evidence storage.

### Prohibited behavior

- Login, account creation, editing, voting, feedback, or form submission other than the read-only search request.
- `POST`, `PUT`, `PATCH`, `DELETE`, uploads, downloads, popups, or new tabs.
- Following external links.
- Crawling multiple pages or running concurrent/repeated load tests.
- Treating an unexpected live-site result as a confirmed Wikipedia accessibility defect without manual reproduction.

Use a descriptive project user agent and run at a conservative rate in accordance with the [Wikimedia User-Agent Policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy).

## 4. Required implementation work

### Work package A — freeze the current baseline

1. Fix the two current provider-related test regressions:
   - the matrix command's changed default provider;
   - run creation when the default live provider is not configured.
2. Make the existing fixture and executor-safety browser tests run reliably from the repository-local temporary directory.
3. Rerun tests, lint, typing, Django checks, and the accessible/broken fixture matrix.

**Gate A:** the existing controlled fixture remains green before any live-target result is accepted.

### Work package B — add a versioned live journey

Create a reviewed journey manifest rather than accepting an arbitrary URL. Store:

- journey ID and version;
- start URL and goal;
- allowed navigation and resource origins;
- allowed path prefixes and methods;
- permitted synthetic input (`search_query: Web accessibility`);
- action, time, page, retry, and planner-call limits;
- prohibited events;
- two completion signals;
- evidence and retention rules.

Seed it through a separate command such as `seed_public_journeys`; do not place an arbitrary-URL field in the UI for this milestone.

**Gate B:** invalid origins, paths, methods, and completion policies are rejected before a browser opens.

### Work package C — generalize observation beyond fixture test IDs

The current observation logic is sufficient for the clinic but too dependent on simple DOM heuristics. Extend it to record, for visible interactive elements:

- accessible role and accessible name;
- associated label and control type;
- editable, enabled, expanded, checked, selected, and required state;
- current focus and `aria-activedescendant` where present;
- destination origin/path for links;
- frame identity;
- a stable evidence fingerprint that does not rely on `data-testid`.

Use Playwright accessibility/ARIA snapshots or browser accessibility semantics where available. Retain `data-testid` only as optional fixture evidence.

**Gate C:** a test page without any `data-testid` attributes can still be observed, navigated, and verified.

### Work package D — harden the local browser boundary

1. Replace `browser.new_page()` with an explicit non-persistent context per run.
2. Install context-wide request routing before the first navigation.
3. Separate allowed document-navigation origins from allowed static-resource origins.
4. Reject state-changing methods, unexpected redirects, unapproved frames, popups, and downloads.
5. Block service workers if they prevent reliable interception.
6. Set a descriptive user agent and fixed viewport/locale/time zone.
7. Close pages and the context on success, timeout, cancellation, or exception.
8. Add a total run deadline, maximum-page count, and no-progress/loop budget.

**Gate D:** automated tests prove that disallowed methods, origins, redirects, popups, and downloads fail closed.

### Work package E — make completion and progress generic

1. Extend completion locators beyond `data-testid` to semantic signals such as:
   - URL path;
   - role plus accessible name;
   - heading level plus text.
2. Require all completion signals to remain valid across the existing stability window.
3. Replace the fixed 150 ms post-key delay with bounded state stabilization based on focus, URL, DOM/accessibility state, and pending navigation.
4. Distinguish these results:
   - effect observed;
   - no effect;
   - wrong effect;
   - focus lost;
   - repeated focus cycle;
   - navigation blocked;
   - execution error.
5. Stop repeated no-progress action/focus patterns instead of spending the full planner budget.

**Gate E:** the Wikipedia result cannot become `completed` from URL alone or heading alone.

### Work package F — prove the live journey

Run the proof in this order:

1. W3C BAD accessible page: small, read-only external smoke run.
2. Wikipedia deterministic/replay run until five consecutive passes.
3. Wikipedia live-planner run until three consecutive non-fallback passes.
4. Deliberately alter the expected heading and verify the result is not `completed`.
5. Deliberately allow the planner to propose an external link and verify the navigation is stopped.
6. Simulate timeout/provider failure and verify it is not reported as a site barrier.

For each accepted run, retain:

- run ID and timestamp;
- exact start and final URL;
- browser and planner versions;
- full keyboard trace;
- focus before/after each action;
- completion-signal evaluations;
- screenshots;
- terminal outcome and reason;
- whether fallback was used.

**Gate F:** all definition-of-done conditions pass from a clean local startup.

## 5. Expected file-level changes

| Area | Expected change |
|---|---|
| `engine/contracts.py` | Add semantic completion locators, target-policy contract, richer element evidence, and additional action-result states. |
| `engine/executor.py` | Use an explicit context, interception, semantic observation, generic completion checks, stabilization, and loop detection. |
| `engine/policy.py` | Enforce navigation/action constraints and prohibited target events. |
| `engine/target_policy.py` | New module for origin, path, method, resource, popup, and download decisions. |
| `apps/journeys/` | Load and validate the reviewed public journey manifest. |
| `fixtures/public/` | Store versioned W3C smoke and Wikipedia journey definitions; no copied site content. |
| `tests/` | Add semantic-observation, routing, completion, loop, and opt-in live-smoke tests. |
| `docs/` | Add a short runbook for the local real-site proof and evidence review. |

The exact filenames may change during implementation, but the policy, observation, execution, and completion responsibilities should remain separate.

## 6. Test structure

### Required on every change

- Unit tests for manifest and completion-policy validation.
- Unit tests for origin, path, method, redirect, popup, and download decisions.
- Local HTML integration tests without `data-testid`.
- Existing accessible and broken clinic regression tests.
- Planner tests using recorded/sanitized Wikipedia-shaped observations rather than hitting the live site.

### Opt-in live tests

Live Wikipedia tests must not run as part of the ordinary unit suite. Require an explicit environment flag such as `RUN_APPROVED_LIVE_TESTS=true`, execute serially, use conservative limits, and retain their evidence separately. A network failure or target change should fail the live-smoke job clearly without making the hermetic test suite flaky.

## 7. Stop conditions

Stop the run immediately when:

- the document attempts to leave the approved origin or path scope;
- a prohibited HTTP method, popup, or download occurs;
- the browser requests credentials or personal information;
- focus/action history enters the configured repetition budget;
- the target presents CAPTCHA or bot-defense interstitials;
- the target layout changes enough that completion cannot be established;
- the planner requests an action outside the typed keyboard schema.

The safe outcome is `safety_stopped` or `inconclusive`, not an improvised workaround.

## 8. Execution order and estimate

For the current three-person team, keep the work sequential at the integration points:

1. Baseline and manifest contract — 1–2 working days.
2. Semantic observation and completion — 2–3 working days.
3. Browser/network safety boundary — 2–3 working days.
4. Loop handling, evidence, and regression tests — 1–2 working days.
5. External smoke, Wikipedia proof, fixes, and runbook — 1–2 working days.

Expected focused duration: **7–12 working days**, assuming the existing provider and browser environment remain usable.

## 9. Milestone claim after completion

The defensible claim will be:

> AccessPath AI runs locally and can complete a declared, read-only keyboard journey on an approved live website using bounded AI planning and real browser keyboard events, while enforcing target restrictions and producing replayable evidence.

Do not claim general support for arbitrary sites, full keyboard-accessibility coverage, or WCAG conformance from this milestone.
