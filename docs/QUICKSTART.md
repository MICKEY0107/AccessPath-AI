# Quick start

From nothing to a working demo in about five minutes. You need **Docker Desktop**; nothing else. No AI key and no GitHub account are needed for the demo.

## 1. Set up (one command)

Windows (PowerShell, in the project folder):

```powershell
./scripts/dev.ps1 setup
```

macOS or Linux:

```bash
./scripts/dev.sh setup
```

`setup` does the following:

1. Creates `.env` from `.env.example` with a random secret key and database password. An existing `.env` is kept.
2. Builds and starts the containers: database, queue, web app, worker and demo site.
3. Applies the database schema.
4. Downloads axe-core. This is optional, and the setup carries on if it can't download it.
5. Runs `demo_setup`, which creates:
   - a **demo** account
   - 12 demo journeys
   - a demo repository linked to them
   - one team rule
   - six finished reports
6. Prints a system check.

The setup prints the demo account's password **once**. Copy it. To set your own password, run `./scripts/dev.ps1 demo --password <your password>`.

## 2. Open it

Go to <http://127.0.0.1:8000/> and sign in as **demo**. The overview page has a getting-started checklist; the demo has already ticked most of it.

## 3. A five-minute tour

| Click | What you see |
|---|---|
| **Evaluation runs** | The demo journeys and recent runs. Start any journey with **Scripted plan (no AI)**. It finishes in a few seconds. |
| A **Blocked** run (keyboard barrier control) | The report: verdict, "In plain words", findings by WCAG rule. Under **Where to fix**, the exact file and line, with a patch. On **Fixes & re-checks**, press **Verify** to re-run the journey on a patched copy. |
| The library page run | A team rule ("Apply button reached quickly") failing next to the WCAG rules |
| **Rules** | Presets, turning a rule off (a reason is required), ignores that expire, and **Your team's rules** |
| **Active codebase** | The demo repository and the code patterns found before any run. With a token, a real GitHub, GitLab or Bitbucket repository can be cloned here. |
| **Models** | Save an AI key (encrypted, optional), list a provider's models, see which providers may read private code |
| **Status** (top right) | What is set up and how to fix what isn't |

## 4. Add an AI model (optional)

Do any one of these:

- **Groq** (free tier, fast, allowed to read private code): create a key at console.groq.com. Put it in `.env` as `GROQ_API_KEY` and `GROQ_MODEL=openai/gpt-oss-120b`, or paste it on the **Models** page.
- **Local Ollama** (free, private): install Ollama and run `ollama pull llama3.1:8b`. Then set `OLLAMA_BASE_URL=http://host.docker.internal:11434` and `OLLAMA_MODEL=llama3.1:8b` in `.env`, and run `./scripts/dev.ps1 start`.
- **Gemini or OpenRouter:** the same pattern, with the `GEMINI_*` or `OPENROUTER_*` settings.

After changing `.env`, restart with `docker compose up -d`.

## 5. Everyday commands

| Command | What it does |
|---|---|
| `./scripts/dev.ps1 start` / `stop` | Start or stop the containers. Your data is kept. |
| `./scripts/dev.ps1 demo` | Refresh the demo: new reports, nothing deleted |
| `./scripts/dev.ps1 test` | The full test suite (about two minutes) |
| `./scripts/dev.ps1 lint` | ruff |
| `./scripts/dev.ps1 check` | The system check in the terminal |
| `./scripts/dev.ps1 benchmark` | Gate 1 benchmark with the scripted plans. Add `--provider groq --model openai/gpt-oss-120b --repeat 3` to measure an AI planner. |
| `./scripts/dev.ps1 logs` | Follow the worker's log |

On macOS or Linux, use `./scripts/dev.sh` with the same command names.

## Beyond the web app

- **Command line and CI:** `python -m accesspath run journeys/clinic-broken.json --repo .`, plus a GitHub Action for pull requests. See [CLI_AND_CI.md](CLI_AND_CI.md).
- **Coding assistants:** `python -m accesspath mcp`. See [CLI_AND_CI.md](CLI_AND_CI.md#mcp-server-for-coding-assistants).
- **Chrome extension for keyboard and voice users:** load `extension/` unpacked. See [extension/README.md](../extension/README.md).

## If something is wrong

Open **Status**, or run `./scripts/dev.ps1 check`. Every item that isn't ready shows its exact fix. Common cases:

- **Runs stay queued:** the worker isn't running. Start it with `docker compose up -d worker`.
- **Port 8000 is taken:** copy `docker-compose.override.example.yml` to `docker-compose.override.yml` (it moves the app to port 8010), then run `docker compose up -d`.
- **Saved keys stop working** after changing `DJANGO_SECRET_KEY`: save them again on **Models**.
