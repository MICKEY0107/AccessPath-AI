# AccessPath AI architecture and run flow

## What the system evaluates

AccessPath AI checks whether a declared appointment-booking journey can reach its declared completion state through keyboard-only input. The current Phase 1 scope covers motor accessibility on controlled fixture sites. A planner may propose one action at a time, but deterministic policy and the keyboard executor retain control of what can execute and whether the journey truly completed.

## User flow

```mermaid
flowchart LR
    A[Evaluator opens Evaluation runs] --> B[Choose journey]
    B --> C[Choose provider dropdown]
    C --> D{Provider}
    D -->|Gemini| E[Live Gemini plan]
    D -->|OpenRouter| F[Live OpenRouter plan]
    D -->|Deterministic| G[Fixture plan]
    E --> H[Queue evaluation]
    F --> H
    G --> H
    H --> I[Run detail and evidence]
    I --> J{Verified outcome}
    J -->|Completion signal observed| K[Completed]
    J -->|Keyboard barrier observed| L[Blocked]
    J -->|Provider or environment failure| M[Clearly labelled issue]
```

## Backend architecture

```mermaid
flowchart TB
    Browser[Evaluator browser] --> Web[Django web application]
    Web --> Runs[Run creation view]
    Runs --> Postgres[(PostgreSQL: journeys, runs, steps, artifacts)]
    Runs --> Queue[(Redis/Celery queue)]
    Queue --> Worker[Single-concurrency Celery worker]
    Worker --> Service[Run application service]
    Service --> Config[Versioned journey and completion policy]
    Service --> Planner[Bounded planner]
    Planner --> Gate[Process-wide provider pacing gate]
    Gate --> Gemini[Google Gemini API]
    Gate --> OpenRouter[OpenRouter API]
    Planner --> Fixture[Deterministic fixture planner]
    Planner --> Policy[Action policy]
    Policy -->|Approved keyboard action only| Executor[Playwright keyboard executor]
    Policy -->|Rejected| Planner
    Executor --> FixtureSite[Controlled accessible or broken site]
    Executor --> Evidence[Step observations and screenshots]
    Evidence --> Postgres
    Evidence --> Storage[Run-output evidence storage]
    Postgres --> Detail[Run-detail evidence page]
    Storage --> Detail
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
- Gemini and OpenRouter outcomes remain separate evidence sets. Deterministic runs are useful repeatable demonstrations but never count as live-model evidence.
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
