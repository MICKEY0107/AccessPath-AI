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

## Current architecture

The diagram below is the current release and demo architecture. The web product is a
single Django application, while browser and repository work run in separate worker
processes. The command line, GitHub Action and MCP server use the same evaluation
engine, so a finding has the same meaning whichever interface starts it.

```mermaid
flowchart TB
    Evaluator[Evaluator in a browser] --> Web[Django web app\njourneys, runs, evidence and reports]
    KeyboardUser[Keyboard or voice user] --> Extension[AccessPath Assist Chrome extension\nlocal page assistance]
    Extension --> VisitedSite[Visited website]

    CLI[CLI] --> Engine
    GitHub[GitHub Action] --> CLI
    CodingAssistant[Coding assistant] --> MCP[MCP server over stdio]
    MCP --> Engine

    Web --> DB[(PostgreSQL\naccounts, journeys, sessions, runs, steps, findings)]
    Web --> Redis[(Redis\nCelery broker and result backend)]
    Web --> Evidence[(Evidence storage\nscreenshots and exported reports)]
    Redis --> BrowserWorker[Browser worker\ndefault and evaluation queues\none Chromium run at a time]
    Redis --> RepoWorker[Repository worker\nrepository queue]
    BrowserWorker --> RunService[Run orchestration and persistence]
    RepoWorker --> Repository[Read-only repository clone and front-end index]
    RunService --> Engine

    subgraph Engine[Shared evaluation engine]
        Planner[Planner\nlive AI or reviewed scripted plan] --> Pace[Provider pacing gate]
        Pace --> Providers[Groq, Gemini, OpenRouter or Ollama]
        Planner --> Policy[Action and target policy]
        Policy -->|approved keyboard action| Executor[Playwright keyboard executor]
        Policy -->|rejected action| Planner
        Executor --> Checks[Keyboard and page checks\nrule catalog and axe-core]
        Executor -->|possible barrier| Probes[Confirmation probes\nTab walk, target and trap checks]
        Checks --> Findings[Findings and outcome]
        Probes --> Findings
    end

    Executor --> TestedSite[Approved site under test]
    Repository --> Locator[Code locator and reviewable patch]
    Findings --> Locator
    Findings --> DB
    Findings --> Evidence
    Findings --> Outputs[Web report, JSON, Markdown and SARIF]
```

### Production deployment boundary

The repository includes a production-style Compose profile. It is intentionally a
reference configuration: a real cloud deployment supplies managed database, Redis,
object storage, a secret manager, HTTPS gateway and network rules.

```mermaid
flowchart LR
    Internet[People and approved sites] --> Gateway[Managed HTTPS gateway\nTLS and host validation]
    Gateway --> Web[Web service\nGunicorn, non-root, read-only]

    subgraph Private[Private application network]
        Web --> DB[(Managed PostgreSQL\nbackups and recovery)]
        Web --> Redis[(Managed Redis\nprivate broker)]
        Web --> Store[(Private object storage\nevidence lifecycle rules)]
        Redis --> Browser[Browser worker\n2 vCPU, 4 GB, concurrency 1]
        Redis --> Repo[Repository worker\n1 vCPU, 1 GB, concurrency 1]
        Browser --> Store
        Repo --> Store
    end

    Secrets[Secret manager and KMS] --> Web
    Secrets --> Browser
    Secrets --> Repo
    Browser --> Egress[Controlled HTTPS egress\napproved public sites and AI providers]
    Repo --> GitHosts[Allowlisted Git hosts]
    Browser -. blocks .-> PrivateTargets[Loopback, private, link-local\nand cloud metadata addresses]
    Web --> Health[healthz and readyz\nrelease and monitoring checks]
```

The extension is deliberately separate from the evaluation service. It runs fixes,
page checks and optional voice commands inside the person's browser and does not send
page data to AccessPath AI. Chrome speech recognition may process audio according to
Chrome's own permissions and policies.

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

