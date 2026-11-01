# AccessPath AI architecture and run flow

## What the system evaluates

AccessPath AI checks whether a declared journey, on the bundled demo site or a real website, can reach its declared completion state through keyboard-only input. The profile is motor accessibility. A planner (an AI provider, or a reviewed scripted plan) proposes one action at a time; deterministic policy and the keyboard executor keep control of what can execute and whether the journey truly completed. The same engine runs behind the web app, the command line, the GitHub Action and the MCP server.

## User flow (web app)

```mermaid
flowchart LR
    A[Evaluation runs] --> B[Choose journey]
    B --> C[Choose planner]
    C --> D{Planner}
    D -->|Groq, Gemini, OpenRouter, Ollama| E[Live AI plan]
    D -->|Scripted plan, no AI| G[Reviewed or replayed plan]
    E --> H[Queue evaluation]
    G --> H
    H --> I[Report fills in live]
    I --> J{Verified outcome}
    J -->|Completion signal observed| K[Completed]
    J -->|Barrier confirmed by a re-check| L[Blocked]
    J -->|Agent, provider or environment failure| M[Clearly labelled, site not blamed]
```

## Architecture

```mermaid
flowchart TB
    Browser[Person's browser] --> Web[Django web app]
    CLI[Command line] --> Engine
    Action[GitHub Action] --> CLI
    MCP[MCP server] --> Engine
    Web --> Postgres[(PostgreSQL: journeys, sessions, runs, steps, artifacts, findings, repositories, saved keys)]
    Web --> Queue[(Redis / Celery queue)]
    Queue --> Worker[Celery worker, one run at a time]
    Worker --> Service[Run service]
    Service --> Engine
    subgraph Engine[Engine, no Django]
        Planner[Planner] --> Gate[Provider pacing gate]
        Gate --> Providers[Groq / Gemini / OpenRouter / Ollama]
        Planner --> Policy[Action policy]
        Policy -->|approved key only| Executor[Playwright keyboard executor]
        Policy -->|rejected| Planner
        Executor --> Checks[Checks and rule catalog]
        Executor -->|run failed| Probes[Confirm before blaming]
        Checks --> Findings[Findings]
        Probes --> Findings
    end
    Executor --> Site[Site under test, request policy applied]
    Findings --> Postgres
    Findings --> Outputs[Report, JSON/Markdown/SARIF, where to fix]
```

## One evaluation run

```mermaid
flowchart TD
    A[Persist selected provider and model] --> B[Worker starts run]
    B --> C[Capture bounded page observation]
    C --> D[Wait for provider pacing turn]
    D --> E[Request one structured action proposal]
    E --> F{Proposal valid and policy approved?}
    F -->|No| G[Record rejection or bounded provider retry]
    G --> C
    F -->|Yes| H[Execute one keyboard action]
    H --> I[Capture result and screenshot]
    I --> J{Completion or barrier confirmed?}
    J -->|No| C
    J -->|Completion| K[Store completed result]
    J -->|Barrier| L[Store blocked result]
    E -->|Quota, timeout, malformed output, unavailable| M[Labelled contingency or issue outcome]
    M --> N[Store provider metadata and reason]
```

## Provider reliability guardrails

- The UI records the selected provider and model with every run. A run never silently changes provider.
- The worker runs at one task at a time. The pacing gate also applies the configured interval across newly constructed clients, so a new run cannot immediately start another request to the same provider.
- Each provider's results are separate evidence. Scripted runs are useful repeatable demonstrations but never count as live-model evidence.
- Completion requires the declared completion signal. A broken site with a keyboard barrier must remain `blocked`; it must never be reported as a completion.
- `openrouter/free` is suitable for smoke testing only because it can choose different upstream models. Repeatable evidence should use a preflight-verified, fixed model.

## October 2026: from a verdict to a fix

```mermaid
flowchart LR
    Run[Keyboard run] --> Checks[Focus and page checks]
    Checks --> Findings[(Findings with rule, WCAG criterion, element)]
    Run -->|fails| Probe[Confirm before blaming: Tab walk, key probe, trap probe]
    Probe -->|confirmed| Findings
    Probe -->|not confirmed| Agent[Agent or provider failure, with diagnosis]
    Repo[Bound repository] --> Clone[Read-only clone, never run] --> Index[Front-end index]
    Findings --> Locator[Code locator]
    Index --> Locator
    Locator --> Exact[Exact match]
    Locator --> Likely[Likely cause, optional AI search]
    Locator --> Related[Also affected]
    Locator --> Patch[Reviewable patch]
    Patch --> Verify[Verify on a temporary fixture copy]
```

| Module | Responsibility |
|---|---|
| `rules/catalog.json`, `engine/rules.py` | Reviewed rule catalog (WCAG 2.2 + ACT IDs), presets, per-journey settings |
| `engine/checks.py` | Focus visible, focus obscured, unnamed controls, skip links, focus order, on-focus, axe-core |
| `engine/probes.py` | Tab walk, target probe, trap probe used to confirm a barrier |
| `engine/findings.py` | Collects findings, groups copies, applies ignores, gives every rule a result |
| `apps/runs/report.py` | One report for the page and the HTML/JSON exports |
| `engine/repo_clone.py`, `engine/code_index.py`, `engine/secret_scan.py` | Safe clone, front-end index, secret redaction |
| `engine/code_locator.py`, `engine/locator_ai.py` | Where to fix, patches, policy-bound AI search |
| `engine/fix_verify.py` | Re-run a journey against a patched temporary fixture copy |
| `apps/runs/benchmark.py` | Gate 1 measures over the benchmark journeys |

### Product pass (29 October 2026, stage 8)

| Module | Role |
|---|---|
| `engine/rules.py` (`CustomRuleV1`, `CUSTOM_CHECKS`) | Team rules: one of four fixed checks plus a CSS selector, stored in `Journey.rule_config["custom"]`, turned into catalog-shaped rules at run time |
| `engine/checks.py` (`_run_custom`) | Runs team rules once per page, using the page's Tab walk; an invalid selector is reported as not checked |
| `engine/fixture_site.py` | Serves the bundled demo site on its loopback address for a fixture run when nothing else answers there; copies it as the demo repository |
| `apps/codebase/demo.py`, `RepoBinding.source` | The bundled demo repository: analysed in-process, linked to the demo journeys, never cloned |
| `apps/runs/management/commands/demo_setup.py` | One command: demo account, journeys, demo repository, a team rule, scripted runs |
| `apps/core/setup_checks.py` | Shared by the Status page and `check_setup`: database, worker, browser, demo site, axe-core, git, storage, providers, secret key |
| `engine/executor.py` (`_route_web_socket`) | WebSockets follow the same origin policy as requests; a blocked socket is never connected |

### Release 1.0.0 (2 November 2026)

| Module | Role |
|---|---|
| `accesspath/cli.py`, `runner.py`, `report.py`, `journey_file.py` | Command line: journey files, runs without Django, JSON/Markdown/SARIF reports, exit codes, baselines |
| `accesspath/github.py`, `.github/actions/accesspath` | Pull-request comment and the composite GitHub Action |
| `accesspath/mcp_server.py` | MCP server over stdio for coding assistants |
| `accesspath/recorder.py` | `login` (save a signed-in session) and `record` (keys as a scripted plan) |
| `engine/session_state.py`, `apps/journeys/models.py` (`JourneySession`) | Saved sign-ins, encrypted, owner-only, cut to the journey's sites |
| `engine/target_policy.py` | Staging writes: POST only to the start site's origin and paths, within a budget, never redirected elsewhere |
| `apps/runs/services.py` (`persist_steps`) | Live progress: steps saved as they happen |
| `engine/provider_usage.py` | Token and prompt-cache use per run |
| `apps/runs/journey_tools.py` | Journey settings: sign-in, replay plan, baseline, staging writes, journey file |
| `extension/` | AccessPath Assist, the Chrome extension for keyboard and voice users |

