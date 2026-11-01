"""AccessPath as an MCP server for coding assistants (Claude Code, Cursor, and others).

Stdio transport, JSON-RPC 2.0, one message per line, no third-party packages. Tools:

* ``list_journeys``     the journey files in the configured folder
* ``run_journey``       run one (scripted by default) and return findings with file:line
* ``check_page``        page checks on one page of a local site folder or a public URL
* ``get_report``        the last report of a journey
* ``list_rules`` / ``explain_rule``   the rule catalog

Safety: journeys are read only from the configured folder, site folders must sit inside
the repository, keys come only from the server's environment, and nothing is written
outside ``.accesspath/mcp-results`` in the repository.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlparse

from engine.target_policy import is_local_or_private_host

from . import __version__

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
BATCH_VERSIONS = {"2025-03-26", "2024-11-05"}
INSTRUCTIONS = (
    "AccessPath runs keyboard-only accessibility journeys. Use list_journeys, then "
    "run_journey to check a task end to end; each finding names its WCAG rule and, when "
    "found, the file and line to change with a patch. Use check_page after editing a page. "
    "Results describe keyboard operation only and are not a full WCAG audit."
)

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_journeys",
        "description": "List the keyboard journeys available to run.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_journey",
        "description": (
            "Run a journey by keyboard and return the verdict and findings, each with its WCAG "
            "criterion and where to fix it (file, line, patch). Provider 'scripted' replays the "
            "journey's reviewed plan without AI; others plan live with the server's API keys."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "journey": {
                    "type": "string",
                    "description": "Journey file name, e.g. checkout.json",
                },
                "provider": {
                    "type": "string",
                    "enum": ["scripted", "groq", "gemini", "openrouter", "ollama"],
                    "default": "scripted",
                },
                "model": {"type": "string", "description": "Model id for an AI provider"},
                "fail_on": {
                    "type": "string",
                    "enum": ["critical", "serious", "moderate", "minor"],
                },
            },
            "required": ["journey"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_page",
        "description": (
            "Check one page for keyboard problems without a journey: focus order, skip link, "
            "unnamed controls, controls Tab skips, focus that changes the page. Give a site "
            "folder in the repository and a path, or a public URL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "site_dir": {"type": "string", "description": "Folder in the repo, e.g. dist"},
                "path": {"type": "string", "default": "/index.html"},
                "url": {"type": "string", "description": "A public http(s) page instead"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_report",
        "description": "Return the last report saved for a journey.",
        "inputSchema": {
            "type": "object",
            "properties": {"journey": {"type": "string"}},
            "required": ["journey"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_rules",
        "description": "List the WCAG 2.2 keyboard rules AccessPath checks, with presets.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "explain_rule",
        "description": "Explain one rule: what it requires, its WCAG link and how to fix it.",
        "inputSchema": {
            "type": "object",
            "properties": {"rule_id": {"type": "string"}},
            "required": ["rule_id"],
            "additionalProperties": False,
        },
    },
]


class ToolError(ValueError):
    """Shown to the assistant as a tool error (isError), not a protocol error."""


class Server:
    def __init__(self, journeys_dir: Path, repo_dir: Path | None) -> None:
        self.journeys_dir = journeys_dir.resolve()
        self.repo_dir = (repo_dir or Path.cwd()).resolve()
        self.results_dir = self.repo_dir / ".accesspath" / "mcp-results"
        self.protocol_version = ""

    # Paths -------------------------------------------------------------------

    def _journey_path(self, name: str) -> Path:
        path = (self.journeys_dir / name).resolve()
        if self.journeys_dir not in path.parents or path.suffix.lower() not in {
            ".json",
            ".yml",
            ".yaml",
        }:
            raise ToolError("Give a journey file name from list_journeys.")
        if not path.is_file():
            raise ToolError(f"No journey named {name}.")
        return path

    def _inside_repo(self, folder: str) -> str:
        path = (self.repo_dir / folder).resolve()
        if path != self.repo_dir and self.repo_dir not in path.parents:
            raise ToolError("The site folder must be inside the repository.")
        if not path.is_dir():
            raise ToolError(f"No folder {folder} in the repository.")
        return str(path)

    # Tools -------------------------------------------------------------------

    def list_journeys(self, _args: dict) -> dict:
        from .journey_file import load_journey

        journeys = []
        for path in sorted(self.journeys_dir.glob("*")):
            if path.suffix.lower() not in {".json", ".yml", ".yaml"}:
                continue
            try:
                journey = load_journey(path)
            except Exception as error:  # A broken file is listed with its problem.
                journeys.append({"file": path.name, "error": str(error)[:200]})
                continue
            journeys.append(
                {
                    "file": path.name,
                    "name": journey.name,
                    "goal": journey.goal,
                    "start": journey.start_url or f"{journey.site_dir}{journey.start_path}",
                    "scripted_plan": bool(journey.plan),
                }
            )
        return {"journeys": journeys}

    def run_journey(self, args: dict) -> dict:
        from .journey_file import load_journey
        from .report import build_summary, to_markdown
        from .runner import RunConfigError, run_journey

        path = self._journey_path(str(args.get("journey", "")))
        journey = load_journey(path)
        out = self.results_dir / path.stem
        try:
            output = run_journey(
                journey,
                base_dir=path.parent,
                provider=str(args.get("provider") or "scripted"),
                model=str(args.get("model") or ""),
                out_dir=out,
                repo_dir=self.repo_dir,
            )
        except RunConfigError as error:
            raise ToolError(str(error)) from None
        summary = build_summary(output, fail_on=args.get("fail_on"), journey_path=path.name)
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        (out / "summary.md").write_text(to_markdown(summary), encoding="utf-8")
        return _compact(summary)

    def check_page(self, args: dict) -> dict:
        from .runner import scan_page

        site_dir, url = args.get("site_dir"), args.get("url")
        if bool(site_dir) == bool(url):
            raise ToolError("Give either site_dir (with path) or url.")
        if url:
            parsed = urlparse(str(url))
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ToolError("url must be an http or https address.")
            if is_local_or_private_host(parsed.hostname):
                # Local and private addresses (including cloud metadata) are refused;
                # check local pages through site_dir instead.
                raise ToolError("url must be a public address; use site_dir for local pages.")
        path = "/" + str(args.get("path") or "index.html").lstrip("/")
        result = scan_page(
            base_dir=self.repo_dir,
            site_dir=self._inside_repo(str(site_dir)) if site_dir else None,
            path=path,
            url=str(url) if url else None,
            out_dir=self.results_dir / "scan",
        )
        findings = [
            {
                "rule_id": item.rule_id,
                "wcag": item.wcag_criterion,
                "severity": item.severity,
                "status": item.status,
                "summary": item.summary,
                "element": (item.element.model_dump() if item.element else None),
            }
            for item in result.findings
        ]
        return {"findings": findings, "count": len(findings)}

    def get_report(self, args: dict) -> dict:
        name = Path(str(args.get("journey", ""))).stem
        report = (self.results_dir / name / "report.json").resolve()
        if self.results_dir.resolve() not in report.parents or not report.is_file():
            raise ToolError("No saved report for that journey yet; run it first.")
        return _compact(json.loads(report.read_text(encoding="utf-8")))

    def list_rules(self, _args: dict) -> dict:
        from engine.rules import load_catalog

        catalog = load_catalog()
        return {
            "catalog_version": catalog.catalog_version,
            "presets": {preset.id: preset.rules for preset in catalog.presets},
            "rules": [
                {
                    "id": rule.id,
                    "title": rule.title,
                    "wcag": rule.wcag.criterion,
                    "level": rule.wcag.level,
                    "severity": rule.default_severity,
                }
                for rule in catalog.rules
            ],
        }

    def explain_rule(self, args: dict) -> dict:
        from engine.rules import load_catalog

        try:
            rule = load_catalog().rule(str(args.get("rule_id", "")))
        except KeyError:
            raise ToolError("Unknown rule id; see list_rules.") from None
        return {
            "id": rule.id,
            "title": rule.title,
            "summary": rule.summary,
            "wcag": f"{rule.wcag.criterion} {rule.wcag.name} (level {rule.wcag.level})",
            "url": str(rule.wcag.url),
            "act_rules": [str(item.url) for item in rule.act_rules],
            "how_to_fix": rule.fix_hints,
        }

    # Protocol ----------------------------------------------------------------

    def handle(self, message: dict) -> dict | None:
        method = message.get("method")
        message_id = message.get("id")
        if method is None:
            return None  # A response from the client (we send no requests): ignore it.
        if message_id is None:
            return None  # Notifications (initialized, cancelled) need no reply.
        try:
            if method == "initialize":
                requested = (message.get("params") or {}).get("protocolVersion")
                version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
                self.protocol_version = version
                result: dict[str, Any] = {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "accesspath", "version": __version__},
                    "instructions": INSTRUCTIONS,
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                result = self._call(message.get("params") or {})
            else:
                return _error(message_id, -32601, f"Method not found: {method}")
        except Exception as error:  # Never let one request stop the server.
            traceback.print_exc(file=sys.stderr)
            return _error(message_id, -32603, f"Internal error: {type(error).__name__}")
        return {"jsonrpc": "2.0", "id": message_id, "result": result}

    def _call(self, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handlers = {tool["name"]: getattr(self, tool["name"]) for tool in TOOLS}
        if name not in handlers:
            return {"content": [{"type": "text", "text": f"Unknown tool {name}."}], "isError": True}
        if not isinstance(arguments, dict):
            return {
                "content": [{"type": "text", "text": "Arguments must be an object."}],
                "isError": True,
            }
        try:
            data = handlers[name](arguments)
        except ToolError as error:
            return {"content": [{"type": "text", "text": str(error)}], "isError": True}
        except Exception as error:  # noqa: BLE001 - tool failures are results, not protocol errors
            traceback.print_exc(file=sys.stderr)
            text = f"The tool failed: {type(error).__name__}: {str(error)[:300]}"
            return {"content": [{"type": "text", "text": text}], "isError": True}
        return {
            "content": [{"type": "text", "text": json.dumps(data, indent=2)}],
            "structuredContent": data,
        }


def _compact(summary: dict) -> dict:
    """What an assistant needs: the verdict and each finding with where to fix it."""
    findings = []
    for row in summary["findings"]:
        if row.get("ignored"):
            continue
        locations = row.get("locations") or {}
        fix = locations.get("fix") or {}
        where = [
            {"path": item["path"], "line": item["line"], "confidence": item.get("confidence")}
            for column in ("exact", "likely")
            for item in (locations.get(column) or [])[:2]
        ]
        findings.append(
            {
                "rule_id": row["rule_id"],
                "title": row.get("rule_title", row.get("title")),
                "wcag": row.get("wcag_criterion"),
                "severity": row["severity"],
                "status": row["status"],
                "summary": row["summary"],
                "where_to_fix": where,
                "patch": fix.get("patch") or None,
                "fix_steps": fix.get("steps") or row.get("fix_hints") or [],
            }
        )
    return {
        "journey": summary["journey"]["name"],
        "verdict": summary["verdict"],
        "diagnosis": summary.get("diagnosis", ""),
        "findings": findings,
    }


def _error(message_id: Any, code: int, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": text}}


def serve(
    journeys_dir: Path,
    repo_dir: Path | None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    server = Server(journeys_dir, repo_dir)
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            reply: dict | None = _error(None, -32700, "Parse error")
        else:
            if isinstance(message, list):
                # Batches were dropped from MCP in 2025-06-18; older versions allow them.
                if not message or server.protocol_version not in BATCH_VERSIONS:
                    reply = _error(None, -32600, "Invalid request")
                else:
                    replies = [
                        server.handle(m)
                        if isinstance(m, dict)
                        else _error(None, -32600, "Invalid request")
                        for m in message
                    ]
                    reply = [r for r in replies if r] or None  # type: ignore[assignment]
            elif isinstance(message, dict):
                reply = server.handle(message)
            else:
                reply = _error(None, -32600, "Invalid request")
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()
    return 0
