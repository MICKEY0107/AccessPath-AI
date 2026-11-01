# Command line, CI and coding assistants

The web app is one way to use AccessPath. The same engine also runs from a terminal, in GitHub Actions on every pull request, and inside coding assistants over MCP. None of these needs the server or the database.

Run commands from the AccessPath folder. From anywhere else, set `PYTHONPATH=/path/to/AccessPath-AI`.

```bash
python -m accesspath --help
```

## Journey files

A journey is one JSON file. YAML also works when PyYAML is installed. `python -m accesspath init` writes an example.

```json
{
  "schema_version": "accesspath_journey.v1",
  "name": "Checkout",
  "goal": "Add the first product to the basket and open the checkout page, by keyboard.",
  "start_url": "https://staging.shop.example/",
  "success": {"url_contains": "/checkout"},
  "type_values": {"search": "blue mug"},
  "rules": {"preset": "wcag22-aa", "fail_on": "serious"},
  "max_steps": 40
}
```

| Field | Meaning |
|---|---|
| `start_url` or `site_dir` + `start_path` | A live page, or a folder of static files in the repository. A folder is served on a local port, which suits a built site in CI. |
| `success` | `url_contains` and/or `text_present`. A run passes only when the goal is really reached. |
| `type_values` | The only text the AI may type, for example search terms. |
| `plan` | A scripted plan: the keys to press. It replays without AI (`--provider scripted`). |
| `rules` | Same as the Rules page: preset, `fail_on`, `disabled`, `severity`, `ignores`, team rules in `custom`. |
| `allowed_origins` | Other sites the journey may navigate to. The default is the start site only. |
| `session` | A saved sign-in file, for pages behind a login (see below). |
| `staging_writes` | `true` only for a staging site you control: allows up to 5 POST requests to the start site's allowed paths. Background POSTs (analytics, GraphQL) count too and are blocked once the budget is spent; a form submitted after that stops the run. A submission that redirects to another site is refused before it is re-sent. |

Live journeys are read-only. Only GET, HEAD and OPTIONS requests are sent, unless `staging_writes` is set. Navigation stays on the allowed sites, and popups and downloads stop the run.

The examples in `journeys/` are:
- the demo clinic (accessible and broken)
- a page without a focus outline
- Wikipedia search
- TodoMVC

## `run`

```bash
python -m accesspath run journeys/clinic-broken.json --repo . --out results
python -m accesspath run journeys/wikipedia-search.json --provider groq --model openai/gpt-oss-120b
python -m accesspath run fixtures/benchmark/journey-manifest.json --key bench-no-focus-style
```

Options:
- **Planner.** `--provider scripted` (default), `groq`, `gemini`, `openrouter` or `ollama`. Keys come from `GROQ_API_KEY` (and the matching variables for the others), or from the variable named by `--api-key-env`. The model comes from `--model` or `GROQ_MODEL`, and so on.
- **Code mapping.** `--repo .` maps every finding to a file and line in that checkout, with a patch where the fix is mechanical. Nothing leaves the machine.
- **Output.** `--out results` writes `report.json`, `summary.md` (the pull-request comment) and `results.sarif`. Choose the formats with `--format json,markdown,sarif`.
- **Gate.** `--fail-on serious` sets the lowest severity that fails.
- **Baselines.**
  - `--write-baseline baseline.json` saves this run as a baseline.
  - `--baseline baseline.json` fails only on findings that are new since then.
- **Other options.**
  - `--session session.json` uses a saved sign-in.
  - `--axe vendor/axe-core/axe.min.js` adds axe-core page rules.
  - `--headed` shows the browser.
  - `--no-fail` always exits 0.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Passed, or only items that need a person |
| 1 | Failing: a confirmed finding at or above `fail_on` |
| 2 | Blocked: a confirmed keyboard barrier stops the task |
| 3 | Incomplete: the AI or the environment stopped the run, and the site was not blamed |
| 4 | Setup problem: bad journey file, missing key and so on |

## Signed-in pages

```bash
python -m accesspath login https://staging.shop.example/account --out session.json
```

1. A browser window opens. Sign in by hand, then press Enter in the terminal.
2. The session (cookies and storage) is saved to `session.json` with owner-only file permissions. Your password is never seen.
3. Treat the file like a password and keep it out of git.

Use the file with `--session session.json`, or upload it on the journey's **Journey settings** page. It is cut down to the journey's own sites before use.

## Record and replay

```bash
python -m accesspath record https://shop.example/ --out journeys/checkout.json --success-url /checkout
```

Use only the keyboard in the window that opens, then close it. Every key (Tab, Shift+Tab, Enter, Space, Escape, arrows) becomes the journey's plan, and `run` replays it without AI. Typing in a field is saved as the field's final text, so corrections replay correctly. Password and card fields are never recorded: for pages behind a login, use `login` and `--session`. Without `--success-url` or `--success-text`, the page the recording ended on becomes the success check.

In the web app, **Journey settings → Save as replay plan** does the same from any run that completed the journey, including an AI run. **Download as a journey file** gives the file for the CLI.

## GitHub Actions

`.github/actions/accesspath` is a composite action. It installs the engine and Chromium, runs each journey, and then:
- uploads SARIF to code scanning, so findings appear on the pull request at the line to fix
- keeps one summary comment on the pull request up to date (it never adds duplicates)
- fails the job when a journey is blocked, failing or incomplete

```yaml
permissions:
  contents: read
  pull-requests: write      # the summary comment
  security-events: write    # code scanning
jobs:
  journeys:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/accesspath           # or MICKEY0107/AccessPath-AI/.github/actions/accesspath@<tag>
        with:
          journeys: journeys/*.json
          provider: scripted                          # or groq with api-key: ${{ secrets.GROQ_API_KEY }}
          fail-on: serious
          baseline: .accesspath/baselines             # optional: <journey>.json files from earlier runs
```

The action's other inputs are `model`, `api-key`, `repo-path`, `comment`, `upload-sarif`, `fail` and `name`. Give each call in a workflow its own `name`: each keeps its own pull-request comment, and each journey gets its own code-scanning category. Its outputs are `exit-code` and `results-dir`. SARIF paths are relative to the repository root, even when `repo-path` is a subfolder. The comment escapes `@mentions` and drops query strings from page addresses. This repository uses it in `.github/workflows/accesspath-journeys.yml`:
- the accessible clinic journey is the gate
- the demo barrier journeys are reported without failing

## MCP server for coding assistants

```bash
python -m accesspath mcp --journeys journeys --repo .
```

The server speaks MCP over stdio. To add it to Claude Code, run this from the AccessPath folder:

```bash
claude mcp add accesspath -- python -m accesspath mcp --journeys journeys --repo .
```

For Cursor and other clients, use the same command in their MCP settings, with `cwd` set to the repository, or `PYTHONPATH` set to the AccessPath folder.

| Tool | What it does |
|---|---|
| `list_journeys` | The journeys in the folder |
| `run_journey` | Runs one (scripted by default) and returns the verdict and each finding, with WCAG criterion, file, line and patch |
| `check_page` | Page checks on one page of a site folder in the repository, or on a public URL (local and private addresses are refused), with no journey needed |
| `get_report` | The last saved report of a journey |
| `list_rules` / `explain_rule` | The rule catalog and how to fix each rule |

The server reads journeys only from the configured folder and site folders only inside the repository. It uses only the API keys in its own environment, and writes only under `.accesspath/mcp-results`.
