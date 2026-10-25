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
