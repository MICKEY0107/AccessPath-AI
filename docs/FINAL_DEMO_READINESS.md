# AccessPath AI final demo readiness

**Status date:** 21 November 2026
**Scope:** Keyboard-first AccessPath AI release. This is not a claim of full WCAG conformance or a completed multi-disability product.

## Release evidence

| Evidence | Latest result | Status |
|---|---|---|
| Local stack readiness | Database, worker, Chromium, fixture site, axe-core, repository storage and hosted-provider configuration ready | Passed |
| Code quality | Ruff passed; Pyright reported 0 errors and 0 warnings | Passed |
| Interface verification | Extension, CLI, MCP and public-pilot command: 25 tests passed | Passed |
| Full regression suite | 278 passed, 9 opt-in public-site tests skipped, 0 failed (21 November 2026) | Passed |
| Deterministic benchmark | 36 of 36 expected outcomes matched; all five benchmark targets met at 100% (21 November 2026) | Passed |
| Live public-site proof | Groq completed the approved Wikipedia journey in 6 keyboard steps: run `0e6b7a00-91ee-41b2-9dbb-8d6438f45b18` | Passed |
| Strict three-run live proof | A later Groq attempt hit the provider's token-per-minute quota and ended `environment_blocked / RUN_TIMEOUT`; the site was not blamed | External capacity limit |

## What is ready to demonstrate

- Web product: journeys, rules, reports, evidence, code mapping, suggested patches and temporary-copy verification.
- Keyboard checks: reachability, traps, focus visibility and obstruction, names, skip links, focus order, on-focus behavior and axe-core page checks.
- Developer delivery: CLI reports in JSON, Markdown and SARIF; exit codes; baselines; GitHub Action definition; MCP server; record/replay and saved-session support.
- Chrome extension: focus ring, landmarks, keyboard repairs, control naming, page checks and voice-command implementation.
- Offline, repeatable demonstration: the scripted clinic and benchmark journeys.
- Live AI evidence: one approved, read-only Groq/Wikipedia completion. Its report must remain available as the internet/provider backup.

## Final release checklist

### Ready now

- [x] Clean Docker build and local stack startup.
- [x] Database migration check and demo data refresh.
- [x] axe-core installation.
- [x] Lint and type check.
- [x] Extension, CLI, MCP and public-pilot automated tests.
- [x] Full regression suite: 278 passed, 9 intentional opt-in skips.
- [x] One live read-only Groq public-site completion.
- [x] Three-repeat deterministic benchmark: 36 of 36 expected outcomes matched.
- [x] Deterministic demo reports, source mapping, patch and temporary-copy verification.

### Requires a human or an external service

- [ ] In Google Chrome, load `extension/`, allow microphone permission and manually confirm voice commands. This cannot be proved by a headless browser test.
- [ ] Re-run the three-run Groq proof after the provider quota resets, or preflight and use another approved provider. Do not describe a scripted run as live-AI evidence.
- [ ] Authenticate to GitHub, create a demonstration branch and pull request, then confirm the existing GitHub Action's summary comment and SARIF upload.
- [ ] Connect `python -m accesspath mcp --journeys journeys --repo .` to the intended coding assistant and perform one interactive tool call.
- [ ] Have a second person perform the demo checklist and record their feedback.
- [ ] Finalise team/institution details, rehearse to the assigned presentation duration and create the release tag after the demonstrated commit is committed.

## Live-demo sequence

1. Run `./scripts/dev.ps1 check` and open the Status page.
2. Sign in to the local app as `demo`.
3. Show an accessible clinic report, then the blocked clinic report.
4. Show the confirmed Tab-walk evidence, `fixtures/clinic/broken/slots.html:6`, the generated patch and **Fix verified**.
5. Show the saved Groq/Wikipedia report to distinguish live AI evidence from the scripted demo.
6. Show the Chrome extension in normal Chrome. Use keyboard repairs and voice only after microphone permission was manually tested.
7. Show the CLI output and prepared GitHub pull-request evidence.
8. Finish with the 36-run deterministic benchmark and state its scope accurately.

## Safe fallback

If a live provider rate-limits or the public internet is unavailable, show the saved Groq report and say: "The live provider is unavailable. AccessPath records that as a provider or environment failure; it does not blame the website." Then use the controlled scripted clinic journey for the reliable product demonstration.

## Commands

```powershell
./scripts/dev.ps1 start
./scripts/dev.ps1 demo --password "AccessPathDemo!2026"
./scripts/dev.ps1 check
./scripts/dev.ps1 benchmark --provider fixture --repeat 3
./scripts/dev.ps1 lint
./scripts/dev.ps1 type
./scripts/dev.ps1 test
```

For the approved live proof after quota is available:

```powershell
docker compose exec -T -e RUN_APPROVED_LIVE_TESTS=true web python manage.py run_public_pilot --provider groq --count 3 --confirm-approved-target
```
