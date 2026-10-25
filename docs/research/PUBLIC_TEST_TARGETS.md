# AccessPath AI: Safe Public Test Targets and Demo-Fixture Strategy

**Research date:** 25 September 2026  
**Decision scope:** keyboard-only autonomous navigation for the initial 5–6 day implementation milestone  
**Status:** implementation-planning input; not a claim of WCAG conformance or legal advice

## Executive recommendation

Use a three-layer target portfolio:

1. **Guaranteed demonstration:** a team-owned local Django fixture that supports a complete, reversible appointment-booking journey.
2. **Cross-site proof:** read-only, bounded runs against official sites that are expressly published as accessibility demonstrations, primarily W3C WAI BAD and Deque University demo pages.
3. **Regression controls:** official pattern examples and a pinned accessibility-failure corpus for repeatable detector tests.

The complete booking or form submission must happen only on the team-owned fixture. A public URL is not permission to create accounts, submit forms, make bookings, send messages, upload files, or perform payments. Public targets should support the claim that the engine can inspect and navigate more than one site, not carry the milestone's success criteria.

This approach preserves the important product claim—Gemini can plan bounded keyboard actions on unfamiliar pages—without making the demo dependent on third-party availability, changing markup, network access, or unapproved side effects.

## 1. Guaranteed target: a team-owned local fixture

Build an original fixture called **AccessPath Clinic** and run it on a separate local origin from the product application, for example:

- AccessPath AI product: `http://localhost:8000`
- Target fixture: `http://fixture.localhost:8001`

Keeping the fixture on another origin proves that the evaluator is driving an external target rather than manipulating its own UI directly.

### 1.1 Initial journey

The fixed journey should be:

1. Open the clinic home page.
2. Navigate to appointment services.
3. Select a service.
4. Select a date and seeded appointment slot.
5. Complete a short multi-step form using synthetic values.
6. Review the appointment.
7. Confirm a **simulated** booking.
8. Reach a deterministic confirmation page and record the reference ID.

No email, SMS, payment provider, calendar integration, or external API should be called. Confirmation should write only synthetic data to the local development database or session, and the fixture must provide a one-command reset.

### 1.2 Paired profiles

Expose the same content and business journey in two controlled profiles:

| Profile | Purpose | Expected result |
|---|---|---|
| Accessible baseline | Positive control for navigation and completion | The keyboard agent completes the journey with a logical focus path and no keyboard blocker |
| Barrier profile | Negative control for detection and recovery | The agent records known barriers, safely recovers where possible, and reports an incomplete journey when a blocker is intentional |

Seed a small number of deliberate motor/keyboard barriers with known IDs and expected outcomes. Suitable cases are an illogical focus order, an element that looks clickable but is not keyboard operable, suppressed focus styling, focus loss after a step transition, and one isolated keyboard-trap scenario. The trap must have a watchdog that terminates the run; never let an autonomous run loop indefinitely.

Maintain a machine-readable expectation manifest for these barriers. It should identify the fixture version, route, expected WCAG success criterion, reproduction keys, expected detector result, and whether the journey should remain completable. This lets the team measure precision and regressions instead of relying on an impressive-looking video.

### 1.3 Why this must be the milestone gate

- The team owns the authorization boundary and can safely exercise the full journey.
- The markup, data, and expected result are stable.
- The fixture can run without internet access if the review environment is unreliable.
- Both successful navigation and known failure handling can be demonstrated.
- Test data can be reset before every run.
- It produces evidence that can later become automated integration tests.

The fixture should be original. Do not copy and modify W3C pages without checking the applicable license: WAI generally permits copying complete materials with attribution but restricts derivative modification unless a resource carries a more permissive license ([W3C WAI permission guidance](https://www.w3.org/WAI/about/using-wai-material/)).

## 2. Recommended public demonstration targets

### 2.1 W3C WAI Before and After Demonstration (primary)

**Official entry point:** [W3C WAI Before and After Demonstration](https://www.w3.org/WAI/demos/bad/)

W3C describes BAD as a multi-page inaccessible site and a retrofitted accessible version. It expressly identifies presentations, practical accessibility examples, assistive-technology browsing, and conformance-report examples as uses. That makes it the strongest external demonstration target for this project.

Recommended routes:

- [Inaccessible home](https://www.w3.org/WAI/demos/bad/before/home.html)
- [Accessible home](https://www.w3.org/WAI/demos/bad/after/home.html)
- [Inaccessible survey](https://www.w3.org/WAI/demos/bad/before/survey.html)
- [Accessible survey](https://www.w3.org/WAI/demos/bad/after/survey.html)

Recommended tasks:

- Move through the main navigation with keyboard actions and record the focus sequence.
- Compare reachability, focus visibility, and ordering between the before and after pages.
- Navigate into the survey controls and demonstrate a known difference in tab order.
- Run axe-core and distinguish automated findings from the manual keyboard evidence.
- Stop before submitting the live survey.

W3C's Easy Checks explicitly uses BAD pages for accessibility practice, including the survey for forms and the accessible survey for visible focus ([W3C Easy Checks](https://www.w3.org/WAI/test-evaluate/preliminary/)).

Limitations:

- BAD is dated 2012 and is framed around WCAG 2.0, so it is not a complete current WCAG 2.2 oracle.
- W3C states that the survey requires PHP and that submission does not work in a local static copy.
- It illustrates selected barriers, not every accessibility requirement.
- Its public availability does not justify unbounded crawling or repeated submissions.

Use BAD for read-only comparative proof, not as the end-to-end milestone gate.

### 2.2 Deque University demonstration sites (secondary)

**Official entry point:** [Deque University Demo Sites](https://dequeuniversity.com/demo/)

Deque states that the listed sites are for teaching accessibility and for use as test cases in automated and manual accessibility assessments. This provides a clear first-party basis for bounded evaluation.

The most useful initial page is:

- [MarsCommuter demo](https://dequeuniversity.com/demo/mars/)
- [MarsCommuter accessibility notes](https://dequeuniversity.com/demo/mars/notes)

The page contains navigation and booking-style controls, and Deque's notes describe intentional keyboard issues such as an illogical tab order. A suitable task is to enter the page, traverse a small fixed number of focus stops, identify that the first focus target violates expected reading order, and stop before any booking/search submission.

Limitations:

- The host and content belong to a third party and may change or be unavailable.
- Intentional failures can confuse an unconstrained agent; step and time limits are mandatory.
- Links may lead away from the intended demo scope.
- Do not submit a booking, contact form, login, or any other state-changing control.

### 2.3 W3C ARIA Authoring Practices examples (component controls)

**Official entry point:** [WAI-ARIA APG patterns](https://www.w3.org/WAI/ARIA/apg/patterns/)

APG provides functional examples and expected keyboard interaction models for components such as dialogs, menus, radio groups, tabs, toolbars, listboxes, and grids. Use a small curated set as positive controls for the action executor—for example, confirming that `Tab` moves between components while arrow keys move within a composite widget, as described in [Developing a Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/).

APG is not a realistic end-to-end booking journey. W3C also says its examples are illustrative rather than a comprehensive design system or production-ready code ([APG introduction](https://www.w3.org/WAI/ARIA/apg/about/introduction/)). Use it to validate keyboard mechanics, not to claim broad real-site autonomy.

### 2.4 UK Government accessibility-tool audit (regression corpus)

The official [GDS accessibility-tool-audit repository](https://github.com/alphagov/accessibility-tool-audit) contains accessibility failures specifically for testing automated accessibility tools, includes instructions for serving the corpus locally, and is MIT licensed. Its [published results](https://alphagov.github.io/accessibility-tool-audit/results.html) also illustrate why automated detectors do not find every class of issue.

Pin a specific commit and host selected cases locally as detector regression tests. This is a failure corpus, not a natural user journey, so it belongs in automated validation rather than the main presentation flow.

## 3. Public-target safety policy

The product must enforce safety independently of the AI planner. The planner proposes an action; a deterministic policy guard decides whether the executor may perform it.

### 3.1 Required target manifest

No public run should start from an arbitrary URL during the initial implementation. Each approved target needs a reviewed manifest containing:

- exact allowed origin and path prefixes;
- target owner and official purpose;
- approved task description;
- allowed navigation destinations;
- allowed HTTP methods;
- maximum pages, steps, duration, and retries;
- whether controlled text entry is permitted;
- prohibited controls and stop conditions;
- review date and reviewer;
- evidence-retention policy.

Redirects and new windows must be checked against the same allowlist before continuing.

### 3.2 Permitted third-party behavior

- Anonymous access to expressly public demo pages.
- Normal document and asset retrieval.
- Keyboard focus traversal using `Tab`, `Shift+Tab`, arrow keys, `Enter`, `Space`, and `Escape` when the manifest permits them.
- Controlled, synthetic text entry only when it cannot submit or store data.
- DOM/accessibility-tree inspection, screenshots, focus traces, and locally injected axe-core evaluation.
- One browser context, one run at a time, with conservative page, step, and time limits.

### 3.3 Prohibited third-party behavior without written authorization

- Account creation or login.
- Submission of forms that send or persist data.
- Appointment or booking confirmation.
- Payments, purchases, reservations, or checkout.
- Sending messages, email, notifications, or feedback.
- Uploading or downloading user files.
- Entering real personal, financial, health, or credential data.
- Deleting or modifying data.
- CAPTCHA bypass, authentication bypass, access-control probing, vulnerability scanning, or evasion of rate limits.
- Unbounded crawling or following links to an unapproved origin.

### 3.4 Network enforcement

For public-target mode, allow only the minimum methods needed for document retrieval—normally `GET` and `HEAD`, with `OPTIONS` only if proven necessary—and abort `POST`, `PUT`, `PATCH`, `DELETE`, `CONNECT`, and other unapproved methods. RFC 9110 classifies `GET`, `HEAD`, `OPTIONS`, and `TRACE` as safe methods, but the project should still disallow `TRACE` because it is unnecessary here ([RFC 9110, HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-safe-methods)).

Playwright Python supports browser-context or page request routing and explicit request abortion, which can implement this guard ([Playwright Python network interception](https://playwright.dev/python/docs/network), [Route.abort](https://playwright.dev/python/docs/api/class-route#route-abort)). Use context-level routing so popups and additional pages are covered, disable service workers for predictable interception, and fail closed when the method or origin is unknown.

Network method filtering is necessary but not sufficient: some poorly designed sites attach side effects to `GET`. The target manifest and control-level classifier must therefore also block labels and destinations associated with submit, send, buy, reserve, confirm, delete, download, upload, and login actions.

### 3.5 Robots, terms, and authorization

Review the site's terms and, when the behavior amounts to crawling, its `robots.txt` before adding it to the allowlist. Honor an applicable disallow rule. RFC 9309 explicitly says robots rules are not a form of access authorization, so an allow rule—or the absence of a disallow rule—is not blanket permission for autonomous actions ([RFC 9309, Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309.html)).

If target ownership or permitted use is ambiguous, do not automate it. Ask the owner for written permission or use the local fixture. Random production websites should not appear in the demonstration.

## 4. Keyboard-testing oracle for the current scope

The initial motor-accessibility profile should evaluate at least these WCAG 2.2 success criteria:

- **2.1.1 Keyboard:** functionality is operable through a keyboard interface.
- **2.1.2 No Keyboard Trap:** focus can move away from a component using the keyboard.
- **2.4.3 Focus Order:** focus moves in an order that preserves meaning and operability.
- **2.4.7 Focus Visible:** the keyboard focus indicator is visible.
- **2.4.11 Focus Not Obscured (Minimum):** the focused component is not entirely hidden by author-created content.

These requirements come from the normative [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/). Passing this profile must be reported as **keyboard-profile results**, not “WCAG compliant.” WCAG conformance applies to complete pages and processes and includes many criteria outside the current visual/audio-later scope.

Use the [W3C Easy Checks keyboard procedure](https://www.w3.org/WAI/test-evaluate/preliminary/#keyboard) as the manual comparison protocol. It directs testers to use `Tab` and `Shift+Tab`, arrow keys within controls, and `Enter` or `Space` for selection, and to check reachability, escape from every focusable element, logical order, visible focus, and full keyboard functionality. W3C cautions that Easy Checks are preliminary and not a comprehensive evaluation.

For the multi-step fixture, follow W3C's [Multi-page Forms guidance](https://www.w3.org/WAI/tutorials/forms/multi-page/): logical step grouping, repeated instructions where needed, clear progress, recognizable optional steps, and no unnecessary time limit.

## 5. Demonstration sequence

Use this sequence so the demo remains credible even if the internet fails:

1. Start from the AccessPath AI home page and explain the keyboard-only motor profile.
2. Select the local accessible fixture, state the goal in natural language, and show Gemini selecting from a constrained action set.
3. Complete the appointment journey while displaying the current focus target, proposed action, policy decision, and captured evidence.
4. Run the same goal against the barrier profile; show one recovered issue and one bounded blocker/report outcome.
5. Show the run comparison and expected-versus-observed barrier evidence.
6. If network access is available, run a short read-only W3C BAD comparison.
7. Optionally run a bounded focus-order check on Deque MarsCommuter to demonstrate cross-domain portability.

The planner should be autonomous within the permitted action vocabulary; it must not control scope, authorization, network policy, timeouts, or side-effect approval. “Autonomous” should mean goal-directed selection among allowed keyboard actions, not unrestricted control of a public browser.

## 6. Acceptance criteria for target readiness

The target layer is ready for the project demonstration only when all of the following are true:

- The local fixture can be reset and seeded deterministically.
- The accessible profile completes the full booking journey three consecutive times.
- The barrier profile produces the expected evidence without hanging the worker.
- The browser executor uses keyboard input for journey interaction; DOM inspection may inform planning but does not directly invoke target JavaScript actions.
- Every run has hard limits for steps, pages, duration, retries, and origin changes.
- The public mode aborts every unapproved method and cross-origin navigation.
- The public demonstration performs no login, submission, booking, messaging, payment, upload, or data modification.
- External-target failure does not prevent the local demo from succeeding.
- Reports identify the target, target version or retrieval time, browser version, keyboard profile, action trace, findings, limitations, and whether a human review is still required.
- The UI never labels a partial automated or keyboard-only result as full WCAG compliance.

## 7. Final target selection

For the 5–6 day milestone, implement and present these targets in order:

1. **Required:** original local AccessPath Clinic accessible and barrier profiles.
2. **Required supporting proof:** W3C BAD accessible and inaccessible home/survey pages, navigation-only.
3. **Preferred supporting proof:** Deque MarsCommuter, bounded focus-order inspection only.
4. **Automated regression support:** selected WAI-ARIA APG examples and pinned GDS failure cases.

Do not spend the first sprint generalizing to arbitrary public websites. A narrow allowlisted target adapter, a real AI planning loop, strict keyboard execution, reliable evidence, and a controlled end-to-end fixture demonstrate feasibility more professionally than an unsafe or flaky “works everywhere” claim.
