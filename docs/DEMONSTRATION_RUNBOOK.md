# AccessPath AI demonstration runbook

**Rehearsal target:** 8 minutes  
**Status:** Prepared against the verified local revision. The dashboard now uses a provider dropdown and a process-wide pacing guard; replace this timing only when the mentor confirms the official duration.  
**Demonstrated evidence:** accessible run `af03b14a-6700-4b91-a437-b8e3ada1de83`; blocked run `cf0e9180-6cd1-4d08-a7f1-972eba776d56`

## Before the room

1. Run `docker compose up -d` and confirm all five services with `docker compose ps`.
2. Run `docker compose exec -T worker celery -A config inspect ping` and require one `pong`.
3. Open `http://127.0.0.1:8000/runs/` and preload the two demonstrated run-detail URLs in separate tabs.
4. Keep the strict-matrix result and the progress log available. Do not start a live provider run unless there is at least ten minutes of buffer; model latency is external and variable.
5. Close notifications and unrelated windows. Keep browser zoom at 100%.

## Exact eight-minute flow

| Time | Screen/action | What to say | Proof point |
|---|---|---|---|
| 0:00–0:40 | Homepage or dashboard overview | “AccessPath AI asks a narrow question: can this declared journey be completed with keyboard-only interaction? Phase 1 uses controlled accessible and deliberately broken twins.” | Scope is motor accessibility and a controlled appointment journey. |
| 0:40–1:30 | Point to the journey cards and planner dropdown | “I explicitly choose Gemini, OpenRouter, or deterministic mode. A live provider proposes one typed action from a bounded observation. Deterministic policy decides whether it is safe; Playwright executes only the keyboard schema; the completion oracle, not the model, decides the outcome.” | Provider choice, policy authorization, execution, and outcome are separate. |
| 1:30–3:20 | Open accessible run `af03b14a-6700-4b91-a437-b8e3ada1de83` | Read the header: `Completed`, Live Gemini, 29 calls, completion policy satisfied. Scroll through two representative steps and their focus-before/focus-after evidence. | One complete accessible booking with `fallback_used=false`. |
| 3:20–4:20 | Open a screenshot and press Right Arrow, then Escape | “Every executed step retains before/after screenshots and a hash. The gallery is keyboard-operable too.” | Evidence chain and keyboard-accessible review UI. |
| 4:20–5:50 | Open blocked run `cf0e9180-6cd1-4d08-a7f1-972eba776d56` | Read `Blocked`, Live Gemini, 13 calls, and `KEYBOARD_TARGET_NOT_REACHABLE`. Scroll to the red issue-evidence screenshot. “The system did not claim success when the target was unreachable.” | Broken-site classification and zero false completion for this run. |
| 5:50–6:45 | Return to dashboard, then show progress log summary | “The full suite passes after the latest Docker verification: 48 tests plus lint, type, Django, migration, and browser checks. Progress is 33.5%, not 35%, because the final uninterrupted provider-pure 3+5 matrix is still an exit gate.” | Evidence-weighted status; no inflated completion claim. |
| 6:45–7:30 | Show architecture diagram/slide if available; otherwise keep dashboard visible | “The safety boundary is deterministic. Supported actions are Tab, Shift+Tab, Enter, Space, arrow keys, and bounded text entry. Unsupported or policy-rejected proposals are recorded and never executed.” | Bounded action surface and auditability. |
| 7:30–8:00 | Limitations slide or this section | “Current limits: controlled fixtures, one motor-access profile, local deployment, provider variability, and no production transaction. Public-target and broader accessibility profiles are later phases.” Then invite questions. | Honest scope and next work. |

## If live Gemini is slow or unavailable

Do not relabel deterministic fallback as Gemini or OpenRouter evidence. Show the two persisted live-Gemini run details above, point to the planner metadata and run IDs, and explain that the visible deterministic adapter is a continuity mechanism rather than evaluation evidence. If a newly started run falls back, show its fallback label and return to the persisted proof.

## Presenter hand-offs

- `LEAD_INTEGRATION`: 0:00–1:30 and 5:50–7:30.
- `AI_ML`: 1:30–4:20, including typed planner and no-fallback metadata.
- `QA_FIXTURE`: 4:20–5:50 and 7:30–8:00, including barrier evidence and limitations.

Replace role IDs with names after the binding roster is completed. Rehearse once with verbal hand-offs and once with a forced provider-outage contingency.

## Pass criteria for the rehearsal

- Finish between 7:30 and 8:00 without skipping limitations.
- Both run IDs are visible and read correctly.
- The blocked result is never described as a failed test; it is the expected negative-control outcome.
- The accessible result is never described as Gemini-only unless its metadata says `fallback_used=false`.
- At least one screenshot is opened, advanced with Right Arrow, and closed with Escape.
- The presenter states that 33.5% is current and 35% requires the final strict matrix and exit review.
