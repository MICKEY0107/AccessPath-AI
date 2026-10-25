# Local real-site keyboard pilot runbook

This runbook executes the reviewed, read-only Wikipedia journey from the local AccessPath AI stack. It does not enable arbitrary URLs, login, editing, submission, downloads, popups, or external navigation.

## Target and completion

- Start: `https://en.wikipedia.org/wiki/Main_Page`
- Goal: open the `Web accessibility` article using keyboard actions only.
- Completion requires both:
  - URL path `/wiki/Web_accessibility`;
  - level-one heading `Web accessibility`.

The target contract is `fixtures/public/journey-manifest.json`. Review changes to that file before every target-policy change.

## One-time local preparation

```powershell
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_fixture_journeys
docker compose exec web python manage.py seed_public_journeys
```

Open `http://127.0.0.1:8000/runs/`, select **Wikipedia — find the Web accessibility article**, choose a configured planner, and start the evaluation. Choose **Deterministic fixture contingency** for the reviewed replay path.

## Deterministic five-run proof

Set the opt-in flag only for the command invocation:

```powershell
docker compose exec -e RUN_APPROVED_LIVE_TESTS=true web python manage.py run_public_pilot --provider fixture --count 5 --confirm-approved-target
```

Every run must report `completed`. Review each run page for its keyboard trace, focus evidence, completion signals, blocked background requests, screenshots, browser version, manifest version, and terminal reason.

## Live-provider three-run proof

Use one provider that has already passed its provider preflight. Do not mix providers inside the proof.

```powershell
docker compose exec -e RUN_APPROVED_LIVE_TESTS=true web python manage.py run_public_pilot --provider gemini --count 3 --confirm-approved-target
```

`openrouter` or `groq` may replace `gemini` when its exact configured model has passed preflight. A run using deterministic fallback does not count as live-provider evidence; the command fails in that case.

## Native opt-in proof

The normal test suite skips public network tests. To run them intentionally in PowerShell:

```powershell
$env:RUN_APPROVED_LIVE_TESTS='true'
$env:LIVE_PLANNER_PROVIDER='gemini'
$env:EVALUATOR_BROWSER_EXECUTABLE='C:\Program Files\Google\Chrome\Application\chrome.exe'
uv run pytest -q tests/test_live_public_site.py
```

Unset the opt-in variable afterward or open a fresh shell.

## Expected safe behavior

- Background state-changing requests such as telemetry are aborted and recorded as policy events.
- A state-changing document navigation stops the run.
- Unapproved navigation origins and paths stop the run.
- Popups and downloads stop the run.
- Repeated focus cycles stop before the action budget is exhausted.
- Provider, network, and page-layout failures are not reported as accessibility barriers.

If Wikipedia changes its resource origins or focus order, do not broaden the policy automatically. Review the new request or keyboard trace, update the versioned manifest only when justified, and rerun the hermetic suite before repeating the public proof.
