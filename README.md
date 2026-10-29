# AccessPath AI

AccessPath AI evaluates whether a declared digital journey can be completed using a keyboard-only accessibility profile. The current implementation targets motor accessibility.

## Quick start

You need Docker Desktop. No AI key and no GitHub account are needed to try it.

```powershell
./scripts/dev.ps1 setup        # Windows   (macOS/Linux: ./scripts/dev.sh setup)
```

Then open <http://127.0.0.1:8000/> and sign in as **demo** with the password the setup printed. The demo has twelve journeys, a linked demo repository, a team rule and six finished reports. Start with the **Blocked** report: it names the file and line to fix and can verify the patch.

| Guide | For |
|---|---|
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | Setup, a five-minute tour, everyday commands, fixing common problems |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | Reading a report (product managers) and setting up journeys, rules, code and models (developers) |
| [docs/ADAPTING.md](docs/ADAPTING.md) | Settings, extension points (rules, checks, providers, code patterns, hosts), testing |
| [docs/DEMONSTRATION_RUNBOOK.md](docs/DEMONSTRATION_RUNBOOK.md) | The 10-minute presentation demo |

## What it does

AccessPath runs a declared task on a website using only the keyboard and returns a verdict a developer or product manager can act on:

1. **Run the journey.** An AI planner (Groq, Gemini, OpenRouter, or local Ollama) proposes one keyboard action at a time; a deterministic policy approves each one before Playwright presses the key.
2. **Check every step.** Focus visible (2.4.7), focus not hidden (2.4.11), unnamed controls (4.1.2, checked against Chromium's accessibility tree), skip links (2.4.1), focus order (2.4.3), focus that changes the page (3.2.1), and axe-core on each page when installed.
3. **Confirm before blaming.** When a run fails, deterministic probes re-check the target: a Tab walk from the top of the page, Enter and Space (with a mouse click only as a comparison), and a Tab/Shift+Tab/Escape trap test. Only a confirmed barrier is reported against the site; otherwise the run says it was an agent or provider failure and why.
4. **Report.** The run page is an accessibility report: verdict, plain-language summary for product managers, findings mapped to WCAG rules from a reviewed catalog, fixes, the AI's reasoning, and the full keyboard evidence. Export it as HTML or JSON.
5. **Point to the code.** Link the site's repository on the **Code** page. AccessPath clones it read-only, indexes the front end, and shows each finding's exact file and line, likely causes and other affected places, with a reviewable patch. Fixes to the bundled fixture pages can be verified on a temporary copy.

## Pages

| Tab | What it is for |
|---|---|
| Overview | What AccessPath does and a getting-started checklist (with a **Load the demo** button) |
| Evaluation runs | Start journeys, add a real website, see recent runs |
| Rules | Pick a preset (Essential, WCAG 2.2 AA, Strict) per journey, turn rules off with a reason, change severities, add ignores that expire, add your team's own rules (four fixed checks plus a CSS selector) |
| Active codebase | Bind a GitHub, GitLab or Bitbucket repository and branch to a live site, or use the bundled demo repository; see code patterns that often break keyboard access |
| Models | Choose provider and model, list the provider's models, optionally remember an encrypted key; see which providers may read private code |
| Report (per run) | Findings map with where-to-fix, fixes and re-checks, AI reasoning, evidence, exports |
| Status | What is set up (database, worker, browser, demo site, axe-core, git, AI providers) and the exact fix for anything that is not; `python manage.py check_setup` in a terminal |

## Local setup (step by step)

`./scripts/dev.ps1 setup` does all of this; these are the individual steps.

1. Install Docker Desktop with WSL2/Linux containers.
2. Copy `.env.example` to `.env` and replace local-only placeholder values.
3. Build and start: `docker compose up --build -d` (rebuild after pulling: the image installs `git` for the Code page).
4. Apply the schema, create your account, and seed the journeys:

   ```powershell
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py createsuperuser
   docker compose exec web python manage.py seed_fixture_journeys
   docker compose exec web python manage.py seed_public_journeys
   docker compose exec web python manage.py install_axe_core   # optional, adds axe-core page rules
   docker compose exec web python manage.py demo_setup         # optional: demo account, repository, reports
   ```

5. Open `http://127.0.0.1:8000/runs/` and sign in. Start the accessible clinic journey, then the keyboard-barrier control.

Every page requires sign-in because the app stores repositories and saved API keys. Journeys and runs are shared by everyone signed in; repositories and saved keys belong to each person. Code locations, snippets and patches from a linked repository are shown (and exported) only to the person who linked it, only they can map or verify fixes, and the AI code search runs only on runs that person started. Linking a repository never takes over a journey someone else has linked.

## Benchmark (Gate 1)

`seed_fixture_journeys` also seeds twelve benchmark journeys with known expected results: the two clinic journeys and ten pages under `fixtures/clinic/benchmark/`, each with one known barrier (div button, cookie-dialog trap, removed focus outline, focus under a fixed header, unnamed icon buttons, no skip link, focus that navigates, mouse-only button) or none (two references).

```powershell
docker compose exec worker python manage.py run_benchmark --provider fixture --repeat 3
docker compose exec worker python manage.py run_benchmark --provider groq --model openai/gpt-oss-120b --repeat 3
```

The command prints the Gate 1 measures (trustworthy outcomes, barrier precision, known barriers found, repeatability, runs within free-tier limits) and saves the summary as JSON. With the scripted plans all 36 runs match their expected results; the live run measures the AI planner itself.

## Security of the Code page

- Only `https` URLs on github.com, gitlab.com or bitbucket.org; no credentials in the URL.
- The access token is used once for the clone, travels encrypted to the worker, is passed to git in an HTTP header, and is never stored.
- Shallow, single-branch clone with hooks off, symlinks as plain files, no submodules or LFS, no redirects (so the token header cannot follow one), and a time limit that kills git's helper processes too. File count and size are checked from the tree before any file is written, then again after checkout; the `.git` folder is deleted and nothing in the repository is ever run.
- Fix verification serves only AccessPath's own `fixtures/clinic/` pages, never files from a clone.
- `.env` files, keys and build folders are never read; secrets are redacted from whole files before any line is shown (so multi-line private keys are caught), from the index, and from every snippet and patch.
- The AI code search runs only with providers allowed to read private code (Ollama, Groq; add others with `CODE_SAFE_PROVIDERS`), may only search and read indexed files under a step-by-step policy, and treats repository text as untrusted data.
- Clones live in the `repo_storage` volume, outside the media folder, so they are never served.

## Local Ollama

Set `OLLAMA_BASE_URL` (from Docker: `http://host.docker.internal:11434`) and `OLLAMA_MODEL`, pull the model with `ollama pull <model>`, and choose **Local Ollama** in the run form. No API key is needed and nothing leaves your machine.

The reviewed live-site pilot is the read-only Wikipedia journey. It remains opt-in and
runs from the local stack; see `docs/RUNBOOK_REAL_SITE_PILOT.md` for the exact safety
boundary, deterministic five-run proof, and live-provider three-run proof.

## Choosing the provider, model, and API key per run

Each journey's run form lets you pick Gemini, OpenRouter, Groq, or the deterministic fixture. For a live provider you can also type:

- **Model**: the exact model id for this run. Leave it blank to use `GEMINI_MODEL`, `OPENROUTER_MODEL`, or `GROQ_MODEL` from `.env`.
- **API key**: a key used for this run only. Leave it blank to use the provider key from `.env`.

To reuse a key, save it on the **Models** page with “Remember on this computer (encrypted)”: it is stored as Fernet ciphertext with its own key context, shown only as `••••abcd`, and used only for your own runs. A run uses the typed key first, then your saved key, then the server key. A typed key is never saved. The web process encrypts it with a key derived from `DJANGO_SECRET_KEY` and passes only the ciphertext to the worker through the task (it expires after an hour). The worker decrypts it in memory and scrubs it from step evidence, planner metadata, error detail, and any re-raised error. The run page shows only whether your key or the server key was used, plus its last four characters.

## Evaluating a real website

On the runs page, open **Evaluate a real website** and add a journey: a start page, a plain-language goal, at least one success check (the address contains some text, or the page shows some text), and optionally a value the evaluator may type, such as a search term. Then start it with Gemini, OpenRouter, or Groq.

These runs reuse the public pilot's fail-closed policy. Only GET, HEAD, and OPTIONS requests are allowed, so nothing is ever submitted. Navigation stays on the site's own address and any extra addresses you list. Popups and downloads stop the run. Images, fonts, and scripts may load from any public CDN, but private and local hosts are blocked, and the start page must resolve to a public address (set `ALLOW_PRIVATE_NETWORKS=true` only for your own local test sites). Real-site journeys have no scripted replay, so a provider failure ends the run as an agent error with the provider's reason. Remove a journey from the dashboard when you are done; its past runs are kept.

## Why live runs fall back, and what the planner does about it

A one-off bad answer (an empty or truncated completion, an unroutable model, or invalid JSON) is retried up to `PLANNER_MAX_INVALID_RETRIES` times before the run switches to its contingency. Rate limits wait for the provider's `Retry-After` (or its "try again in" hint) and get up to three patient retries. A bad key or unknown model fails at once. The run page shows the provider's own error message. `openrouter/free` picks a random free model for every call and is unreliable for multi-step journeys, so the form warns about it; pin a specific model instead.

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
