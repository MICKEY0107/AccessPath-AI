"""The MCP server for coding assistants (stdio JSON-RPC, no extra packages)."""

from __future__ import annotations

import io
import json
from pathlib import Path

from accesspath.mcp_server import Server, serve

ROOT = Path(__file__).resolve().parents[1]


def _server(tmp_path: Path) -> Server:
    server = Server(ROOT / "journeys", ROOT)
    server.results_dir = tmp_path / "mcp-results"  # keep test output out of the repo
    return server


def call(server: Server, name: str, arguments: dict, message_id: int = 1) -> dict:
    reply = server.handle(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    return reply["result"]


def test_handshake_and_tool_list_over_stdio(tmp_path: Path) -> None:
    lines = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "nope"},
    ]
    stdin = io.StringIO("\n".join(json.dumps(line) for line in lines) + "\nnot json\n")
    stdout = io.StringIO()
    serve(ROOT / "journeys", ROOT, stdin=stdin, stdout=stdout)
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert len(replies) == 4  # the notification gets no reply
    assert replies[0]["result"]["protocolVersion"] == "2025-03-26"
    names = {tool["name"] for tool in replies[1]["result"]["tools"]}
    assert {"list_journeys", "run_journey", "check_page", "explain_rule"} <= names
    assert replies[2]["error"]["code"] == -32601
    assert replies[3]["error"]["code"] == -32700


def test_run_journey_returns_where_to_fix(tmp_path: Path) -> None:
    server = _server(tmp_path)
    journeys = call(server, "list_journeys", {})["structuredContent"]["journeys"]
    assert any(item["file"] == "clinic-broken.json" for item in journeys)
    data = call(server, "run_journey", {"journey": "clinic-broken.json"})["structuredContent"]
    assert data["verdict"]["key"] == "blocked"
    finding = data["findings"][0]
    assert finding["where_to_fix"][0]["path"] == "fixtures/clinic/broken/slots.html"
    assert finding["patch"].startswith("--- a/fixtures/clinic/broken/slots.html")
    again = call(server, "get_report", {"journey": "clinic-broken"})["structuredContent"]
    assert again["verdict"]["key"] == "blocked"


def test_tools_refuse_paths_outside_their_folders(tmp_path: Path) -> None:
    server = _server(tmp_path)
    for name, arguments in (
        ("run_journey", {"journey": "../pyproject.toml"}),
        ("run_journey", {"journey": "missing.json"}),
        ("check_page", {"site_dir": "../..", "path": "/"}),
        ("check_page", {"url": "file:///etc/passwd"}),
        ("get_report", {"journey": "../../etc"}),
        ("explain_rule", {"rule_id": "nope"}),
    ):
        result = call(server, name, arguments)
        assert result["isError"] is True, (name, arguments)
    assert call(server, "unknown_tool", {})["isError"] is True


def test_check_page_and_rules(tmp_path: Path) -> None:
    server = _server(tmp_path)
    data = call(
        server,
        "check_page",
        {"site_dir": "fixtures/clinic", "path": "/benchmark/nav-no-skip.html"},
    )["structuredContent"]
    assert any(item["rule_id"] == "bypass-blocks" for item in data["findings"])
    rules = call(server, "list_rules", {})["structuredContent"]
    assert len(rules["rules"]) == 9
    rule = call(server, "explain_rule", {"rule_id": "focus-visible"})["structuredContent"]
    assert rule["wcag"].startswith("2.4.7") and rule["how_to_fix"]


def test_protocol_edge_cases(tmp_path: Path) -> None:
    def exchange(version: str, *messages) -> list:
        init = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": version, "capabilities": {}},
        }
        lines = [json.dumps(init), *(json.dumps(item) for item in messages)]
        stdout = io.StringIO()
        serve(ROOT / "journeys", ROOT, stdin=io.StringIO("\n".join(lines) + "\n"), stdout=stdout)
        return [json.loads(line) for line in stdout.getvalue().splitlines()][1:]

    ping = {"jsonrpc": "2.0", "id": 5, "method": "ping"}
    # A response from the client is ignored; an empty batch is an invalid request.
    assert exchange("2025-06-18", {"jsonrpc": "2.0", "id": 9, "result": {}}, []) == [
        {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    ]
    # Batches only for the protocol versions that had them.
    assert exchange("2025-06-18", [ping])[0]["error"]["code"] == -32600
    assert exchange("2025-03-26", [ping])[0] == [{"jsonrpc": "2.0", "id": 5, "result": {}}]


def test_tool_failures_are_results_and_private_urls_are_refused(tmp_path: Path) -> None:
    server = _server(tmp_path)
    for url in ("http://127.0.0.1:8000/", "http://169.254.169.254/latest", "http://localhost/"):
        assert call(server, "check_page", {"url": url})["isError"] is True

    def boom(_args):
        raise RuntimeError("broken")

    server.list_rules = boom
    result = call(server, "list_rules", {})
    assert result["isError"] is True and "RuntimeError" in result["content"][0]["text"]
    # A page path without a leading slash still works.
    data = call(
        server, "check_page", {"site_dir": "fixtures/clinic", "path": "accessible/index.html"}
    )
    assert "findings" in data["structuredContent"]
