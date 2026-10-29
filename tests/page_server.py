"""Serve small in-memory pages to the real browser for engine tests."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from engine.artifacts import LocalArtifactStore
from engine.executor import KeyboardExecutor


@contextmanager
def serve_pages(pages: dict[str, str]):
    """Yield an origin serving ``pages`` (path -> HTML); unknown paths return 404."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            html = pages.get(self.path.split("?", 1)[0])
            if html is None:
                self.send_response(404)
                self.end_headers()
                return
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
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def executor_for(
    origin: str,
    tmp_path: Path,
    *,
    start_path: str = "/",
    signals: list[dict] | None = None,
    barrier_check: dict | None = None,
    max_steps: int = 12,
    no_progress_limit: int = 4,
    rule_set=None,
    on_step=None,
) -> KeyboardExecutor:
    run_id = uuid4()
    return KeyboardExecutor(
        run_id=run_id,
        start_url=f"{origin}{start_path}",
        allowed_origins=[origin],
        target_policy={
            "navigation_origins": [origin],
            "resource_origins": [origin],
            "navigation_path_prefixes": ["/"],
            "no_progress_limit": no_progress_limit,
            "max_actions": max_steps,
        },
        completion_policy={
            "signals": signals or [{"id": "never", "type": "url_path_equals", "expected": "/never"}]
        },
        barrier_check=barrier_check,
        max_steps=max_steps,
        action_timeout_ms=5000,
        headless=True,
        browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=on_step or (lambda step, artifacts: None),
        rule_set=rule_set,
    )
