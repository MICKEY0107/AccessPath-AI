# AccessPath AI presentation outline

## Slide 1: AccessPath AI

Keyboard-only accessibility evaluation for a declared appointment-booking journey.

Show the Evaluation runs screen and state the Phase 1 boundary: controlled fixture sites, motor accessibility, keyboard input, and auditable evidence.

## Slide 2: The evaluation flow

Use the user-flow diagram from `ARCHITECTURE_AND_FLOW.md`.

Explain that the evaluator selects the journey and the provider from one dropdown. Gemini and OpenRouter are live alternatives. Deterministic mode is a visibly labelled contingency, not hidden AI evidence.

## Slide 3: Backend safety boundary

Use the backend architecture diagram.

Emphasise that a model only proposes one typed action. The deterministic policy authorises it, Playwright executes keyboard input only, and the executor verifies the final state.

## Slide 4: Evidence produced by each run

Show one completed run-detail page.

Point to the stored provider/model metadata, step sequence, screenshots, terminal outcome, and evidence hashes. Explain that a completion requires the fixture's declared completion signal.

## Slide 5: Broken-site control

Show a broken fixture run-detail page.

Explain that the keyboard barrier produces `blocked`, not `completed`. This is the safeguard against false-positive accessibility claims.

## Slide 6: Provider reliability and current limitation

Show the provider reliability guardrails from `ARCHITECTURE_AND_FLOW.md`.

State the evidence accurately: Gemini hit quota after valid earlier runs. OpenRouter's free route returned an Nvidia temporary-overload error and one length-limited completion. Neither observed error was an HTTP 429 caused by rapid key reuse. The new process-wide pacing guard removes immediate request starts between runs, but cannot make a free upstream provider available.

## Slide 7: Conclusion and next proof

State the remaining live-evidence gate: one provider, a fixed preflight-verified model, three accessible completions, five broken runs, and zero false completions. Keep Gemini and OpenRouter evidence separate. Show deterministic runs only as the repeatable contingency demonstration.
