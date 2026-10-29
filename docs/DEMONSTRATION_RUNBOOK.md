# AccessPath AI demonstration runbook

**Rehearsal target:** 10 minutes
**Updated:** 29 October 2026, for the web product (rules, team rules, confirmed findings, report, where to fix, one-command demo). The September runbook is in git history.

## Before the room

1. Run `./scripts/dev.ps1 setup` (first time) or `./scripts/dev.ps1 demo` (later). That command:
   - starts everything and applies the schema
   - creates the **demo** account and links the bundled demo repository (nothing is pushed or cloned)
   - adds the team rule "Apply button reached quickly"
   - finishes six reports and prints their links

   Keep these three reports open in tabs:
   - Clinic appointment booking — keyboard-accessible reference (**Passed**)
   - Clinic appointment booking — keyboard barrier control (**Blocked**)
   - Benchmark — library page without a skip link (**Issues found**, including the team rule)
2. Open **Status** and check that everything is **Ready** apart from optional items.
3. Run `./scripts/dev.ps1 benchmark` and keep the output in a terminal.
4. Optional live run, only with at least ten minutes of buffer: Groq `openai/gpt-oss-120b` or local Ollama.

## Ten-minute flow

| Time | Screen | What to say | Proof point |
|---|---|---|---|
| 0:00–0:45 | Evaluation runs | "AccessPath answers one question: can a keyboard user finish this task on this site, and if not, where and why?" | Scope: motor accessibility, keyboard only |
| 0:45–1:45 | Rules | "Rules come from WCAG 2.2 and the W3C ACT rules, shipped as a reviewed catalog. Teams pick a preset, and a rule can only be turned off with a reason; ignores expire. Teams add their own rules from fixed checks — no code." Show the library report's team rule. | Catalog version, ACT IDs, presets, team rule |
| 1:45–3:00 | Accessible clinic report | Read the verdict **Passed**, the plain-words panel, and Fixes & re-checks: every rule passed or not applicable, none silently skipped. | No false positives on the reference journey |
| 3:00–5:00 | Broken clinic report | Verdict **Blocked**. "Before blaming the site, AccessPath re-checked: a Tab walk from the top skipped the time buttons because of tabindex=-1." Open Findings map → Where to fix: `fixtures/clinic/broken/slots.html` lines 6–8. | Confirmed barrier, exact code lines |
| 5:00–6:15 | Fixes & re-checks | Show the patch, press **Copy patch**, then **Verify on a temporary copy**: "the re-run no longer confirms this barrier". "Nothing was applied to the repository." | Find → prove → locate → fix → verify |
| 6:15–7:00 | AI reasoning tab | "The AI only proposes keys; a deterministic policy approves each one. If a run fails and the target turns out to be reachable, the report says agent failure, not site barrier." | Separation of AI and verdict |
| 7:00–8:00 | Terminal: run_benchmark | "Twelve journeys with known barriers. With scripted plans every run matches its expected result; the live run measures the AI planner." | Gate 1 measures |
| 8:00–9:00 | Code and Models | "Repositories are cloned read-only and never run; secrets are redacted. Providers are labelled for whether they may read private code: Ollama and Groq yes, Gemini's free tier no." | Security model |
| 9:00–10:00 | Limitations | Keyboard profile only; read-only on real sites (no form submission yet); code mapping is strongest for static and React/Vue development builds; free-tier limits affect live runs. | Honest scope |

## If a live provider is slow or rate limited

Show the persisted reports. A provider failure is labelled "provider failure" and never counted as a site result. Deterministic runs are labelled as fixture evidence, not AI evidence.

## Pass criteria for the rehearsal

- The accessible report reads **Passed** and the broken one **Blocked**, with the reason shown in plain words.
- Where to fix points at `fixtures/clinic/broken/slots.html` and the verification says resolved.
- The benchmark output is shown, and its offline numbers are described as measuring the checks, not the AI.
- Limitations are stated before questions.
