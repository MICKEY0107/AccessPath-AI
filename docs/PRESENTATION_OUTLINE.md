# AccessPath AI presentation outline

Updated 29 October 2026 for the web product. Pair it with `DEMONSTRATION_RUNBOOK.md`.

## Slide 1: The question

Can a keyboard user finish this task on this site, and if not, exactly where and why? Scanners check single pages; AccessPath walks the whole task.

## Slide 2: How a run works

An AI planner proposes one keyboard action at a time; a deterministic policy approves it; Playwright presses the key. Checks run at every step (focus visible, focus hidden, names, skip links, focus order, focus that changes the page, axe-core).

## Slide 3: Confirm before blaming

Show the broken clinic report. A failed run is re-checked with a Tab walk and key probes. Only a confirmed barrier is reported; otherwise the report says agent or provider failure and why. This is what makes the verdict trustworthy.

## Slide 4: Rules teams can trust

The reviewed catalog: WCAG 2.2 criteria with their W3C ACT rule IDs, three presets, disable-with-reason, ignores that expire. A rule is never "passed" unless it was checked.

## Slide 5: The report for product managers

Verdict, plain-language summary, findings by severity, exports. Show the HTML export opening as a standalone page.

## Slide 6: Where to fix, for developers

Bind the repository. Exact match, likely cause, also affected; a reviewable patch; verification on a temporary copy. Show `fixtures/clinic/broken/slots.html` lines 6–8 and "resolved".

## Slide 7: Security

Read-only clone that is never run, token never stored, secrets redacted, AI code search only with providers allowed to read private code, sign-in on every page.

## Slide 8: Evidence

Benchmark of twelve journeys with known results and the Gate 1 measures. Report offline (checks) and live (AI planner) numbers separately.

## Slide 9: Limits and future scope

Keyboard profile only; read-only on real sites; code mapping strongest for static pages and React/Vue development builds. Future: CLI, MCP server for coding assistants, CI with SARIF and PR comments, record-and-replay, the voice Chrome extension (research).
