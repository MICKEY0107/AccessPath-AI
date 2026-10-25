import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import pytest

from engine.artifacts import LocalArtifactStore
from engine.contracts import ActionKind, ProposedActionV1
from engine.executor import KeyboardExecutor
from engine.planner import FixturePlanPlanner


def _serve_html(html: str) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_executor_rejects_a_start_url_outside_the_approved_origins(tmp_path: Path) -> None:
    run_id = uuid4()
    executor = KeyboardExecutor(
        run_id=run_id,
        start_url="https://unapproved.example/journey",
        allowed_origins=["http://fixture"],
        completion_policy={"signals": []},
        barrier_check=None,
        max_steps=4,
        action_timeout_ms=1000,
        headless=True,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=lambda step, artifacts: None,
    )

    with pytest.raises(ValueError, match="START_URL_NOT_ALLOWED"):
        executor.run(FixturePlanPlanner({"kind": "fixture_plan.v1", "actions": []}).actions())


def test_executor_stops_after_navigation_leaves_the_approved_origin(tmp_path: Path) -> None:
    target_server, target_thread, target_origin = _serve_html("<h1>Unapproved target</h1>")
    source_server, source_thread, source_origin = _serve_html(
        f'<a href="{target_origin}/outside">Leave approved origin</a>'
    )
    try:
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=source_origin,
            allowed_origins=[source_origin],
            completion_policy={
                "signals": [{"type": "url_path_equals", "expected": "/never"}]
            },
            barrier_check=None,
            max_steps=4,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run(
            [
                ProposedActionV1(action=ActionKind.TAB),
                ProposedActionV1(action=ActionKind.ENTER),
            ]
        )

        assert result.outcome == "safety_stopped"
        assert result.terminal_reason == "NAVIGATION_ORIGIN_NOT_ALLOWED"
        assert result.steps_completed == 2
    finally:
        source_server.shutdown()
        target_server.shutdown()
        source_thread.join(timeout=2)
        target_thread.join(timeout=2)


@pytest.mark.parametrize(
    ("html", "expected_reason"),
    [
        (
            '<form method="post" action="/submit"><button type="submit">Submit</button></form>',
            "REQUEST_METHOD_NOT_ALLOWED",
        ),
        (
            '<a href="/popup" target="_blank">Open popup</a>',
            "POPUP_NOT_ALLOWED",
        ),
        (
            '<a href="/file.txt" download>Download file</a>',
            "DOWNLOAD_NOT_ALLOWED",
        ),
    ],
)
def test_executor_fails_closed_for_prohibited_live_target_events(
    tmp_path: Path,
    html: str,
    expected_reason: str,
) -> None:
    server, thread, origin = _serve_html(html)
    try:
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}/wiki/start",
            allowed_origins=[origin],
            target_policy={
                "navigation_origins": [origin],
                "resource_origins": [origin],
                "navigation_path_prefixes": ["/wiki/", "/submit", "/popup", "/file.txt"],
                "allowed_methods": ["GET", "HEAD", "OPTIONS"],
                "allow_popups": False,
                "allow_downloads": False,
                "max_pages": 1,
                "total_timeout_ms": 10_000,
            },
            completion_policy={
                "signals": [
                    {"id": "never", "type": "url_path_equals", "expected": "/never"}
                ]
            },
            barrier_check=None,
            max_steps=4,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run(
            [
                ProposedActionV1(action=ActionKind.TAB),
                ProposedActionV1(action=ActionKind.ENTER),
            ]
        )

        assert result.outcome == "safety_stopped"
        assert result.terminal_reason == expected_reason
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_blocked_background_post_is_evidence_but_does_not_stop_read_only_navigation(
    tmp_path: Path,
) -> None:
    server, thread, origin = _serve_html(
        """
        <a href="/done">Open result</a>
        <script>fetch('/telemetry', {method: 'POST', body: 'ignored'}).catch(() => {});</script>
        """
    )
    evidence = []
    try:
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}/start",
            allowed_origins=[origin],
            target_policy={
                "navigation_origins": [origin],
                "resource_origins": [origin],
                "navigation_path_prefixes": ["/"],
                "allowed_methods": ["GET", "HEAD", "OPTIONS"],
            },
            completion_policy={
                "signals": [{"id": "done", "type": "url_path_equals", "expected": "/done"}]
            },
            barrier_check=None,
            max_steps=4,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: evidence.append(step),
        ).run(
            [
                ProposedActionV1(action=ActionKind.TAB),
                ProposedActionV1(action=ActionKind.ENTER),
            ]
        )

        assert result.outcome == "completed"
        assert any(
            "REQUEST_METHOD_NOT_ALLOWED" in event
            for step in evidence
            for event in step.policy_events
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)
