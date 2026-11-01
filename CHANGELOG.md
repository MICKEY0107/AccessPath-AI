# Changelog

## Unreleased (after 1.0.0)

- `demo_setup` counts and runs only the bundled demo-site journeys, never the public journeys that reach live websites.
- Where to fix: the same attribute on a page other than the one tested is listed under **Also affected**, not as an exact match.
- The "no scripted plan" message names every AI provider, Local Ollama included.
- Docs checked against the code: README, User guide, Adapting guide, Architecture, Demonstration runbook, extension README, handoff and backlog corrected.

## 1.0.0 — 2 November 2026

The first complete release of the web product: it finds keyboard barriers on a journey, confirms them, maps them to WCAG 2.2, and points developers to the line of code to fix.

### Evaluate
- Runs a declared journey using only the keyboard. Each key is proposed by an AI planner (Groq, Gemini, OpenRouter or local Ollama) or by a reviewed scripted plan, and approved by a fixed policy before the browser presses it.
- Checks every step:
  - focus is visible
  - focus is not hidden
  - controls have accessible names
  - skip links work
  - focus order makes sense
  - moving focus does not change the page
  - axe-core page rules, when installed
- Confirms before blaming. A failed run is re-tested without AI (Tab walk, Enter/Space probe, trap probe), and labelled as a site barrier, an agent failure, a provider failure or an environment problem.
- Stops early when the AI repeats the same key on the same control with no effect.

### Rules
- A reviewed catalog of 9 rules, each linked to WCAG 2.2 and, where one exists, to W3C ACT rules (5 of 9), with Essential, WCAG 2.2 AA and Strict presets.
- Per journey, a team can:
  - turn rules off (a reason is required)
  - set each rule's severity
  - choose the severity that fails a run
  - add ignores that expire
  - add its own team rules from four fixed checks plus a CSS selector

### Report
- A verdict and a plain-words summary for product managers.
- Findings by severity and WCAG rule, with a result for every rule; a pass never means "not checked".
- Tabs for fixes, AI reasoning (with token use and prompt-cache hits) and evidence (steps and screenshots).
- HTML and JSON export.

### Code
- Links a GitHub, GitLab or Bitbucket repository. It is cloned read-only and never run:
  - no redirects
  - size checked before any file is written
  - secrets redacted from whole files
- Indexes the front-end code.
- Where to fix: exact match, likely cause and also affected, with a reviewable patch. A policy-bound AI search is used only with providers allowed to read private code.
- Fixes to the bundled demo site can be verified on a temporary copy.
- Code is shown only to the person who linked the repository.

### Beyond the web app
- **Command line** (`python -m accesspath`): run a journey file with no server, map findings to a local checkout, write JSON, Markdown and SARIF, gate with exit codes, and fail only on new findings with baselines. Also `init`, `validate`, `rules`, `login` (save a signed-in session) and `record` (record your own keys as a replayable plan).
- **GitHub Action** (`.github/actions/accesspath`): SARIF in code scanning at the line to fix, one updated summary comment per pull request, and a job gate. An example workflow is included.
- **MCP server** (`python -m accesspath mcp`), with no extra packages: coding assistants can list and run journeys, check a page, read reports and look up rules.
- **AccessPath Assist**, a Chrome extension (MV3) for keyboard and voice users:
  - a strong focus ring
  - skip to main content
  - a landmarks list
  - keyboard fixes for click-only controls
  - names for unnamed buttons
  - voice commands
  - a quick page check

### Journeys
- Signed-in journeys: a saved session, encrypted, owner-only and limited to the journey's sites.
- Record and replay: a completed run becomes a scripted plan, and any journey can be exported as a CLI journey file.
- Baselines: reports show new and fixed findings.
- Staging writes: opt-in and confirmed; POST only to the site's own address, a few per run, and never during a re-check.
- Live run progress: steps are saved as they happen.

### Accounts and models
- Sign-in.
- Models page: list models, save and use a provider, remember a key encrypted, forget it.
- A code-safety badge on each provider.

### Easy to try and adapt
- `./scripts/dev.ps1 setup` (or `dev.sh`) gives a working offline demo: a demo account, 12 journeys, a demo repository, a team rule and six finished reports.
- Status page and `check_setup`.
- Getting-started checklist.
- 12-journey benchmark with Gate 1 measures: 36 of 36 scripted runs match.
- CI workflow, Quickstart, User guide and Adapting guide, and `docker-compose.override.example.yml`.

### Security
- Three independent reviews: 39 issues found; 38 fixed with tests, 1 documented (the worker must keep Celery's default prefork pool).
- Staging writes cannot be redirected to another site, respect the journey's paths, and are never sent during a re-check (WebSockets included).
- Recording never saves password or card fields; session files are created owner-only.
- Signed-in runs and their screenshots are visible only to the person who started them; only the sign-in's owner can change replay plans or staging writes.
- WebSockets follow the same origin policy as other requests.
- Real-site runs are read-only unless the owner turns on staging writes for a site they control.

### Known limits
- Live-AI benchmark numbers and the 3 + 5 course matrix still need to be run on a machine that can reach the AI provider.
- The pitch deck is postponed.
- Keyboard profile only. Forms are submitted only on staging sites whose owner turned it on.
