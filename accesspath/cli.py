"""``python -m accesspath`` — run keyboard journeys from a terminal or CI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__

EXIT_SETUP_ERROR = 4


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load(args) -> tuple[object, Path, str]:
    from .journey_file import journey_from_manifest, load_journey

    path = Path(args.journey)
    if args.key:
        site = args.site_dir or str(Path("fixtures") / "clinic")
        return journey_from_manifest(path, args.key, site), Path.cwd(), str(path)
    return load_journey(path), path.parent, str(path)


def cmd_run(args) -> int:
    from playwright.sync_api import Error as PlaywrightError

    from engine.session_state import SessionStateError, parse_storage_state

    from .report import build_summary, git_relative, to_markdown, to_sarif
    from .runner import RunConfigError, run_journey

    try:
        journey, base_dir, journey_path = _load(args)
    except (OSError, ValueError) as error:
        print(f"accesspath: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    out = Path(args.out)
    session = None
    session_path = args.session or journey.session
    if session_path:
        path = Path(session_path) if args.session else base_dir / session_path
        try:
            session = parse_storage_state(path.read_bytes())
        except (OSError, SessionStateError) as error:
            print(f"accesspath: saved session: {error}", file=sys.stderr)
            return EXIT_SETUP_ERROR
    api_key = os.environ.get(args.api_key_env, "") if args.api_key_env else ""
    baseline = None
    if args.baseline and Path(args.baseline).is_file():
        try:
            baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
            if not isinstance(baseline, dict):
                raise ValueError("not a report")
        except (OSError, ValueError) as error:
            print(f"accesspath: baseline {args.baseline}: {error}", file=sys.stderr)
            return EXIT_SETUP_ERROR
    try:
        output = run_journey(
            journey,
            base_dir=base_dir,
            provider=args.provider,
            model=args.model,
            api_key=api_key,
            out_dir=out,
            repo_dir=Path(args.repo).resolve() if args.repo else None,
            headless=not args.headed,
            browser_executable=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            axe_path=Path(args.axe) if args.axe else None,
            session_state=session,
        )
    except RunConfigError as error:
        print(f"accesspath: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    except (OSError, PlaywrightError) as error:
        # A missing site folder, a browser that will not start and the like: a setup
        # problem (exit 4), never a "failing" site (exit 1).
        print(f"accesspath: could not run the journey: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    summary = build_summary(
        output, fail_on=args.fail_on, baseline=baseline, journey_path=journey_path
    )
    # SARIF paths are relative to the repository root, even when --repo is a subfolder.
    if args.repo:
        summary["code_root"] = git_relative(Path(args.repo))[0]
    if journey_path:
        summary["journey"]["sarif_file"] = git_relative(Path(journey_path))[0] or None
    formats = {item.strip() for item in args.format.split(",") if item.strip()}
    _write(out / "report.json", json.dumps(summary, indent=2))
    if "markdown" in formats:
        _write(out / "summary.md", to_markdown(summary))
    if "sarif" in formats:
        _write(out / "results.sarif", json.dumps(to_sarif(summary), indent=2))
    if args.write_baseline:
        _write(Path(args.write_baseline), json.dumps(summary, indent=2))
    verdict = summary["verdict"]
    print(f"{verdict['label']}: {journey.name}")
    print(f"  {verdict['explanation']}")
    if summary["diagnosis"]:
        print(f"  {summary['diagnosis']}")
    for row in summary["findings"][:10]:
        if row["ignored"]:
            continue
        status = "" if row["status"] == "confirmed" else " (review)"
        print(
            f"  - [{row['severity']}{status}] WCAG {row['wcag_criterion'] or '-'} "
            f"{row['rule_title']}: {row['summary'][:160]}"
        )
    print(
        f"  Reports in {out}/ (report.json"
        + "".join(
            f", {name}"
            for name, key in (("summary.md", "markdown"), ("results.sarif", "sarif"))
            if key in formats
        )
        + ")"
    )
    return 0 if args.no_fail else summary["exit_code"]


def cmd_init(args) -> int:
    from .journey_file import EXAMPLE

    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"accesspath: {path} exists (use --force to replace it)", file=sys.stderr)
        return EXIT_SETUP_ERROR
    _write(path, json.dumps(EXAMPLE, indent=2) + "\n")
    print(f"Wrote {path}. Edit the start page, goal and success check, then:")
    print(f"  python -m accesspath run {path} --provider groq --model openai/gpt-oss-120b")
    return 0


def cmd_validate(args) -> int:
    try:
        journey, _base, _path = _load(args)
    except (OSError, ValueError) as error:
        print(f"accesspath: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    print(
        f"OK: {journey.name} — {len(journey.plan)} scripted step(s), "
        f"preset {journey.rules.get('preset', 'wcag22-aa')}"
    )
    return 0


def cmd_rules(args) -> int:
    from engine.rules import load_catalog

    catalog = load_catalog()
    print(f"Rule catalog {catalog.catalog_version} (reviewed {catalog.reviewed})")
    for rule in catalog.rules:
        presets = [preset.id for preset in catalog.presets if rule.id in preset.rules]
        print(
            f"  {rule.id:<20} WCAG {rule.wcag.criterion:<6} {rule.default_severity:<9} "
            f"{rule.title}  [{', '.join(presets)}]"
        )
    return 0


def cmd_comment(args) -> int:
    from .github import GitHubError, upsert_pr_comment

    body = Path(args.markdown).read_text(encoding="utf-8")
    try:
        url = upsert_pr_comment(
            repository=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
            pull_number=args.pr or 0,
            body=body,
            comment_id=args.id,
            token=os.environ.get("GITHUB_TOKEN", ""),
        )
    except GitHubError as error:
        print(f"accesspath: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    print(f"Comment: {url}")
    return 0


def cmd_login(args) -> int:
    from .recorder import capture_session

    path = capture_session(args.url, Path(args.out))
    print(f"Saved the signed-in session to {path}. Keep it private (it is a password).")
    print("Use it with: python -m accesspath run JOURNEY --session " + str(path))
    return 0


def cmd_record(args) -> int:
    from .recorder import record_journey

    try:
        path = record_journey(
            args.url,
            Path(args.out),
            name=args.name,
            goal=args.goal,
            headless=False,
            success_url=args.success_url,
            success_text=args.success_text,
        )
    except ValueError as error:
        print(f"accesspath: {error}", file=sys.stderr)
        return EXIT_SETUP_ERROR
    print(f"Saved {path}. Replay it with: python -m accesspath run {path}")
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import serve

    return serve(Path(args.journeys).resolve(), Path(args.repo).resolve() if args.repo else None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="accesspath",
        description="Run keyboard-only accessibility journeys and report WCAG findings.",
    )
    parser.add_argument("--version", action="version", version=f"AccessPath AI {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a journey and write JSON, Markdown and SARIF reports.")
    run.add_argument("journey", help="A journey file (JSON or YAML), or a manifest with --key")
    run.add_argument("--key", help="Journey key inside a fixture manifest")
    run.add_argument("--site-dir", help="Static site folder for a manifest journey")
    run.add_argument(
        "--provider",
        default="scripted",
        choices=["scripted", "groq", "gemini", "openrouter", "ollama"],
        help="scripted replays the journey's plan; the others plan live with AI",
    )
    run.add_argument("--model", default="", help="Model id for an AI provider")
    run.add_argument("--api-key-env", default="", help="Read the API key from this env variable")
    run.add_argument("--repo", default="", help="Local checkout to map findings to (file and line)")
    run.add_argument("--out", default="accesspath-results", help="Folder for reports")
    run.add_argument("--format", default="json,markdown,sarif", help="json, markdown, sarif")
    run.add_argument(
        "--fail-on",
        default=None,
        choices=["critical", "serious", "moderate", "minor"],
        help="Lowest severity that fails (default: the journey's rules)",
    )
    run.add_argument("--baseline", help="A previous report.json; only new findings fail")
    run.add_argument("--write-baseline", help="Save this run as a baseline file")
    run.add_argument("--session", help="Saved sign-in (from `accesspath login`)")
    run.add_argument("--axe", help="Path to axe.min.js to add axe-core page rules")
    run.add_argument("--headed", action="store_true", help="Show the browser window")
    run.add_argument("--no-fail", action="store_true", help="Always exit 0 (report only)")
    run.set_defaults(func=cmd_run)

    init = sub.add_parser("init", help="Write an example journey file.")
    init.add_argument("path", nargs="?", default="accesspath-journey.json")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    validate = sub.add_parser("validate", help="Check a journey file without running it.")
    validate.add_argument("journey")
    validate.add_argument("--key")
    validate.add_argument("--site-dir")
    validate.set_defaults(func=cmd_validate)

    rules = sub.add_parser("rules", help="List the rule catalog.")
    rules.set_defaults(func=cmd_rules)

    comment = sub.add_parser("comment", help="Post or update the PR comment (GitHub Actions).")
    comment.add_argument("markdown", help="summary.md from a run")
    comment.add_argument("--repo", help="owner/repo (default: GITHUB_REPOSITORY)")
    comment.add_argument("--pr", type=int, help="Pull request number")
    comment.add_argument(
        "--id", default="", help="Keeps separate comments for separate runs on one PR"
    )
    comment.set_defaults(func=cmd_comment)

    login = sub.add_parser("login", help="Sign in once in a browser window and save the session.")
    login.add_argument("url")
    login.add_argument("--out", default="accesspath-session.json")
    login.set_defaults(func=cmd_login)

    record = sub.add_parser("record", help="Record your own keyboard journey as a replayable plan.")
    record.add_argument("url")
    record.add_argument("--out", default="recorded-journey.json")
    record.add_argument("--name", default="Recorded journey")
    record.add_argument("--goal", default="Replay the recorded keyboard journey.")
    record.add_argument("--success-url", help="Text the final address contains")
    record.add_argument("--success-text", help="Text the final page shows")
    record.set_defaults(func=cmd_record)

    mcp = sub.add_parser("mcp", help="Serve AccessPath to coding assistants over MCP (stdio).")
    mcp.add_argument("--journeys", default="journeys", help="Folder of journey files")
    mcp.add_argument("--repo", default=".", help="Checkout to map findings to")
    mcp.set_defaults(func=cmd_mcp)
    return parser


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))  # So `engine` imports from any working directory.
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)
