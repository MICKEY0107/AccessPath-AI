# User guide

AccessPath answers one question for one task on one website: **can someone who uses only a keyboard finish it?** When the answer is no, it says what to change, and with the code linked, where to change it.

This guide has two parts: reading a report (for product managers and anyone reviewing results) and setting up evaluations (for developers). New here? Start with [QUICKSTART.md](QUICKSTART.md).

---

## Part 1 — Reading a report

Open any run from **Evaluation runs**. The report is in four layers, from the quickest answer to the full evidence.

### The verdict

| Verdict | Meaning | What to do |
|---|---|---|
| **Passed** | The task was finished by keyboard and no rule failed. | Nothing. Re-run after big changes. |
| **Issues found** | The task can be finished, but confirmed problems remain, such as no visible focus. | Plan the fixes. Severity says what comes first. |
| **Blocked** | A keyboard barrier stops the task, and a re-check without AI confirmed it. | Fix this first: these users cannot finish the task at all. |
| **Needs review** | Nothing was confirmed, but some items need a person to look. | Ask someone to check the "to review" items. |
| **Incomplete** | The run stopped before the task could be judged, for example because the AI provider failed. The site was **not** blamed. | Re-run, or try another model. The report says why it stopped. |

**"In plain words"** gives the same answer in two or three sentences you can paste into a ticket. It is written by rules, not by AI, and is labelled that way.

### Confirmed, to review, and ignored

- **Confirmed:** AccessPath proved it, for example by pressing Tab from the top of the page and never reaching the control. Confirmed findings decide the verdict.
- **To review:** a page scan found something that is often a problem but couldn't prove it, such as a control Tab skips that the task may not need. These never fail a run.
- **Ignored:** a known issue someone accepted with a reason and an expiry date (see *Rules*). It stays visible but doesn't fail the run.

### Severity

The levels are **critical**, **serious**, **moderate** and **minor**. Each rule has a default level, and teams can change it. The "Fail the run from" setting on **Rules** decides which levels fail a run. It is *serious and above* by default.

### Rule results

Every rule that was in force shows one result:

- **Passed** means the rule was checked and held.
- **Not applicable** means the pages had nothing it applies to.
- **Not checked** means the run ended before the rule could be tested, or a tool such as axe-core was not installed.

A pass never secretly means "not checked".

### The tabs

| Tab | What is in it |
|---|---|
| **Findings map** | Each finding with its WCAG criterion, the control (name, selector, HTML), how it was confirmed and, with the code linked, **Where to fix** |
| **Fixes & re-checks** | What to change, a patch to copy, **Verify** (for the demo site) and other journeys on the same code that a fix may affect |
| **AI reasoning** | Each key press the AI proposed and why, and whether the policy approved it |
| **Evidence** | Every step with the focused control, the address, and before-and-after screenshots |

### Sharing

- **Export HTML** gives one file with the screenshots inside it. It opens in any browser and can be forwarded or attached to a ticket.
- **Export JSON** is for other tools.

Code from a linked repository appears only for the person who linked it, in exports as well.

---

## Part 2 — Setting up evaluations

### Journeys

A journey is one task: a start page, a goal in plain language, and how to tell it's done.

- **Demo journeys:** twelve tasks on a bundled clinic site, each with a known result. Load them from the overview page, or run `python manage.py demo_setup`.
- **Your own public website:** on **Evaluation runs**, choose **Add a real website**. Give it:
  - a name
  - the start page
  - the goal
  - at least one success check: the address contains some text, or the page shows some text
  - optionally, a value the evaluator may type, such as a search term

  Real-site runs are read-only: no form is ever submitted, nothing outside the site is opened, and private or local addresses are refused.

### Running

Pick a journey and a planner, then press **Run**:

- **Scripted plan (no AI)** replays a reviewed plan. It is only available for the demo journeys and is never counted as AI evidence.
- **Groq**, **Gemini**, **OpenRouter** and **Local Ollama** plan live, one key press at a time.

For a live provider, leave the model and key blank to use the saved or server defaults, or type them for this run only. A typed key is used once and never stored.

### Rules

Rules are set per journey on **Rules**:

1. **Preset**
   - *Essential*: the Level A keyboard blockers.
   - *WCAG 2.2 AA*: the default, and the legal target most teams have.
   - *Strict*: adds advisory focus-appearance checks and axe-core best practices.
2. **Turn a rule off** by unticking it. A reason is required and shows in every report.
3. **Severity** per rule, and **Fail the run from**.
4. **Known issues (ignores):** match a finding by text in its element (a selector or name), give a reason and an expiry date. When the date passes, the issue counts again.
5. **Your team's rules:** add a product-specific rule by choosing one of four fixed checks and a CSS selector. No code is involved.

   | Check | Example |
   |---|---|
   | Must be reachable with Tab | `.buy-button` — every visible match must be a Tab stop |
   | Must have an accessible name | `.icon-button` — every visible match needs a name |
   | Must be reached within N Tab presses | `#checkout` within 5 — the first match must be reached quickly |
   | Must not appear | `div[onclick]` — a pattern your team has banned |

   Each team rule names the WCAG criterion it supports, has a severity and an optional fix text, and appears in reports next to the WCAG rules. A few details:

   - Every visible match is checked, and up to ten failures are listed.
   - "Reachable with Tab" skips the items inside tab lists, menus and grids, because those widgets use one Tab stop plus the arrow keys.
   - An invalid selector shows as "not checked", never as passed.

The catalog behind the WCAG rules (`rules/catalog.json`) ships with AccessPath and names each rule's WCAG 2.2 criterion and W3C ACT rules. It is never fetched while a run is going.

### Linking the code

On **Active codebase**:

- **Demo repository:** one button. It gives you a copy of the demo site's code, linked to the demo journeys.
- **Your repository:**
  1. Paste its GitHub, GitLab or Bitbucket address and a branch.
  2. For a private repository, add a read-only token. It is used once and never stored.
  3. Add the live site's address. Journeys on that site are linked automatically, or tick the ones you want.

What happens to your code:

- It is copied read-only (one branch, latest commit) and never run.
- Size is checked before any file is written.
- `.env` files, keys and build folders are never read.
- Secrets are removed before any line is shown.

Reports then show, for each finding:

- **Exact match:** a line carrying the control's own test id, id, label or framework source hint, and the code pattern the rule looks for.
- **Likely cause:** the control's text or classes. When nothing exact is found, a policy-bound AI search can help, but only with a provider allowed to read private code (Groq or Ollama by default).
- **Also affected:** components that render the file, and the same pattern elsewhere.

For common patterns there is a patch, for example:

- removing `tabindex="-1"`
- turning a clickable `div` into a `button`
- restoring a focus outline
- adding an accessible name

AccessPath never changes your repository: you copy the patch.

### Journey settings

Open **Journey settings** from a journey on Evaluation runs:

- **Signed-in pages:** upload a session saved with `python -m accesspath login <start page>`, and runs you start begin signed in. The password is never seen. The session is encrypted, cut down to the journey's own sites, never shown back, and used only by its owner's runs. While it is saved, only its owner can change the journey's replay plan and staging writes, and the reports of signed-in runs (with their screenshots) are visible only to the person who started them.
- **Record and replay:** save the keys of a run that completed the journey as its replay plan. **Scripted plan (no AI)** then repeats them exactly, as a quick regression test with no AI calls. **Download as a journey file** takes the same journey to the command line and CI ([CLI_AND_CI.md](CLI_AND_CI.md)).
- **Baseline:** pick a run as the baseline. Later reports mark findings that are **New since baseline** and list what was fixed, so a team can stop new barriers before fixing every old one.
- **Staging writes:** off by default. On a staging copy of a site you added, you can allow a few form submissions per run, to your site's own address and paths only, so sign-up or checkout journeys can finish. A submission that redirects to another site is stopped before it is re-sent. You must confirm that the site is yours and not production. The demo journeys always stay read-only.

While a run is going, its report page fills in step by step.

### Models and keys

On **Models**:

- Choose a provider and model and **Save & use** it as your default. **List** shows the provider's models.
- Tick **Remember on this computer** to store the key encrypted for your account only. **Forget key** removes it.
- Each provider shows whether it **may read private code**. The free tiers of Gemini and OpenRouter may not. Groq and local Ollama may. A server admin can allow others with `CODE_SAFE_PROVIDERS`.

### Status

**Status** (top right) checks the database, worker, browser, demo site, axe-core, git, storage and every AI provider, and shows the fix for anything not ready. `python manage.py check_setup` prints the same check in a terminal.

### What AccessPath does not claim

It checks keyboard-only use of the journeys you define, with the rules listed above. It does not test screen-reader output in full, colour contrast beyond axe-core's rules, or pages the journey never visits. A pass is not a WCAG conformance claim.
