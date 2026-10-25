# AccessPath AI

AccessPath AI evaluates whether a declared digital journey can be completed using a keyboard-only accessibility profile. The current implementation targets motor accessibility and begins with a controlled appointment-booking fixture.

## Current phase

The Phase 1 vertical slice is in final evidence review. The run screen offers direct Gemini, OpenRouter, and deterministic-fixture planners. A live provider proposes one typed keyboard action from a bounded observation; deterministic policy authorizes every proposal before Playwright can execute it. A visibly labeled deterministic fixture planner remains the contingency for provider timeout, quota, malformed output, unsafe output, or temporary service failure.

Historical live evidence on 27 September 2026 includes three accessible Gemini completions and five broken-control Gemini runs with zero false completions. Final post-fix individual proofs are run `af03b14a-6700-4b91-a437-b8e3ada1de83` (`completed`, 29 calls, no fallback) and run `cf0e9180-6cd1-4d08-a7f1-972eba776d56` (`blocked`, 13 calls, no fallback). The uninterrupted post-fix 3+5 matrix remains the final Phase 1 gate. The account-discovered model used for those proofs was `models/gemini-3.5-flash-lite`; model availability is account- and time-specific, so always run preflight before changing or enabling it.

## Local setup

1. Install Docker Desktop with WSL2/Linux containers.
2. Copy `.env.example` to `.env` and replace local-only placeholder values.
3. Run `docker compose up --build -d`.
4. Apply the schema and seed the versioned fixture journeys:

   ```powershell
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py seed_fixture_journeys
   docker compose exec web python manage.py seed_public_journeys
   ```

5. Open `http://127.0.0.1:8000/runs/`. Start the accessible journey first, then the keyboard-barrier control.

The reviewed live-site pilot is the read-only Wikipedia journey. It remains opt-in and
runs from the local stack; see `docs/RUNBOOK_REAL_SITE_PILOT.md` for the exact safety
boundary, deterministic five-run proof, and live-provider three-run proof.

## Choosing the provider, model, and API key per run

Each journey's run form lets you pick Gemini, OpenRouter, Groq, or the deterministic fixture. For a live provider you can also type:

- **Model**: the exact model id for this run. Leave it blank to use `GEMINI_MODEL`, `OPENROUTER_MODEL`, or `GROQ_MODEL` from `.env`.
- **API key**: a key used for this run only. Leave it blank to use the provider key from `.env`.

A typed key is never saved. The web process encrypts it with a key derived from `DJANGO_SECRET_KEY` and passes only the ciphertext to the worker through the task (it expires after an hour). The worker decrypts it in memory and scrubs it from step evidence, planner metadata, error detail, and any re-raised error. The run page shows only whether your key or the server key was used, plus its last four characters.

## Gemini preflight and evidence

Keep `GEMINI_API_KEY` in local `.env` only; never commit it or pass it as a command-line argument. Leave `GEMINI_MODEL` blank until discovery succeeds.

```powershell
docker compose exec web python manage.py preflight_gemini --list-only
docker compose exec web python manage.py preflight_gemini --model models/gemini-3.5-flash-lite --calls 3 --interval 15
```

After the exact model passes preflight, set `GEMINI_MODEL` in `.env` and recreate `web` and `worker` so both processes receive it. The strict matrix command accepts only live Gemini results; any deterministic contingency makes the command fail rather than count the run as AI evidence.

The example model above was returned by this account's discovery and passed semantic preflight on 27 September 2026. A separate `gemini-3.1-flash-lite` investigation showed that short preflight success did not reliably translate into useful journey completion for this fixture: runs encountered repeated focus actions, policy rejection, call-limit fallback, and intermittent upstream failures. Discovery alone does not establish free quota or billing status; verify the project's tier in AI Studio. No billing changes are made by this application.

## OpenRouter alternative

OpenRouter is an explicit alternate provider, not a hidden Gemini fallback. Add its credentials only to local `.env`:

```dotenv
OPENROUTER_API_KEY=replace-with-local-key
OPENROUTER_MODEL=replace-with-a-structured-output-model
```

For a low-risk smoke check, `openrouter/free` can route to a currently available free model with the required structured-output parameter. Use a specific preflight-verified model for repeatable evidence, because the free router may select different underlying models. The run detail page records the selected provider/model and, when returned by OpenRouter, the resolved model.

```powershell
docker compose up -d --force-recreate web worker
docker compose exec web python manage.py migrate
docker compose exec web python manage.py preflight_openrouter --model openrouter/free --calls 3 --interval 20
docker compose exec web python manage.py run_fixture_matrix --provider openrouter --accessible-count 1 --broken-count 1
```

After the small proof passes, run the OpenRouter-only strict matrix:

```powershell
docker compose exec web python manage.py run_fixture_matrix --provider openrouter --accessible-count 3 --broken-count 5
```

OpenRouter results are OpenRouter evidence, not Gemini evidence. Never switch providers inside a matrix or call an OpenRouter result “Gemini-only.”

```powershell
docker compose up -d --force-recreate web worker
docker compose exec web python manage.py run_fixture_matrix --accessible-count 3 --broken-count 5
```

The controlled run limits are 40 provider attempts, five retries for transient provider 5xx or timeout failures, a 30-second provider timeout, a 15-second minimum call interval, and 56 executed browser steps. The worker processes one run at a time, and a process-wide provider gate preserves that interval when the next run constructs a fresh client. The broken fixture additionally ends its evidence window after five executed keyboard actions. Policy-rejected proposals are recorded but never executed; Gemini receives another bounded turn instead of silently switching planners.

The evidence-backed project inventory is in `docs/PROJECT_COMPONENT_STATUS.md`; the exact demonstration rehearsal flow is in `docs/DEMONSTRATION_RUNBOOK.md`; the architecture, run flow, and presentation outline are in `docs/ARCHITECTURE_AND_FLOW.md` and `docs/PRESENTATION_OUTLINE.md`.

Preflight uses the same configured transient and quota retry limits as runtime. `--calls` counts successful structured-action checks; retries have a separate bounded attempt allowance. Each successful check prints progress and the attempted-call count. A provider 504 is a temporary upstream deadline failure, not proof of an invalid key. Exhausted retries still fail preflight; do not interpret a passed short check as a guarantee of remaining daily quota or provider availability. Runtime retains the explicitly labelled deterministic fallback.

## Validation commands

```powershell
uv run pytest -q
uv run ruff check .
uv run pyright
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose ps
```

## Stop or reset local services

- Pause services: `docker compose stop`
- Resume services: `docker compose start`
- Stop and remove containers while retaining database data: `docker compose down`
- Remove all local containers and database data (irreversible): `docker compose down -v`

Browser screenshots from the Compose workflow are retained in the shared `run_output` volume and are linked from each run detail page. Native test runs store screenshots under `output/runs/`; both locations are intentionally ignored by Git.

For native Windows browser tests, if Playwright cannot launch its downloaded browser, set `EVALUATOR_BROWSER_EXECUTABLE` to the installed Chrome path before running pytest. Docker uses its bundled Linux Chromium and does not need this setting.

Do not commit `.env`, `.runtime`, browser caches, traces, or screenshots.
