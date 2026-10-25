"""End-to-end evidence tests for the controlled fixture targets."""

from __future__ import annotations

import functools
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

from engine.artifacts import LocalArtifactStore
from engine.contracts import ActionKind, PlannerObservationV1, ProposedActionV1
from engine.executor import KeyboardExecutor
from engine.planner import FixturePlanPlanner, Planner


class RecordingPlanner:
    def __init__(self, delegate: Planner) -> None:
        self.delegate = delegate
        self.observations: list[PlannerObservationV1] = []

    def propose_next_action(self, observation: PlannerObservationV1):
        self.observations.append(observation)
        return self.delegate.propose_next_action(observation)

    def record_outcome(self, observation, action, decision, result) -> None:
        self.delegate.record_outcome(observation, action, decision, result)

    def runtime_metadata(self) -> dict[str, object]:
        return self.delegate.runtime_metadata()


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def _serve_fixture() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "clinic"
    handler = functools.partial(_QuietHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _load_manifest() -> dict:
    path = Path(__file__).resolve().parents[1] / "fixtures" / "clinic" / "journey-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _serve_semantic_journey(
    *, article_heading: str = "Web accessibility"
) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/wiki/Web_accessibility"):
                html = f"<main><h1>{article_heading}</h1><p>Article body</p></main>"
            else:
                html = """
                    <main>
                      <h1>Knowledge site</h1>
                      <form action="/wiki/Web_accessibility" method="get">
                        <label for="search">Search articles</label>
                        <input id="search" name="search" type="search" required>
                        <button type="submit">Search</button>
                        <input id="remember" name="remember" type="checkbox">
                        <label for="remember">Remember choice</label>
                      </form>
                    </main>
                """
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


def test_accessible_fixture_completes_with_keyboard_only(tmp_path: Path) -> None:
    server, thread, origin = _serve_fixture()
    try:
        journey = _load_manifest()["journeys"][0]
        run_id = uuid4()
        evidence = []
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}{journey['start_path']}",
            allowed_origins=[origin],
            completion_policy=journey["completion_policy"],
            barrier_check=journey["evaluation_config"].get("barrier_check"),
            max_steps=24,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: evidence.append((step, artifacts)),
        ).run(
            FixturePlanPlanner(
                journey["evaluation_config"]["planner"]["fallback"]
            ).actions()
        )

        assert result.outcome == "completed"
        assert result.terminal_reason == "COMPLETION_POLICY_SATISFIED"
        assert evidence
        assert all(step.evidence_source == "keyboard_observation" for step, _ in evidence)
        type_steps = [
            step for step, _ in evidence if step.proposed_action.action.value == "type"
        ]
        assert type_steps
        assert all(step.action_result.meaningful_progress for step in type_steps)
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_broken_fixture_reports_keyboard_barrier(tmp_path: Path) -> None:
    server, thread, origin = _serve_fixture()
    try:
        journey = _load_manifest()["journeys"][1]
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}{journey['start_path']}",
            allowed_origins=[origin],
            completion_policy=journey["completion_policy"],
            barrier_check=journey["evaluation_config"].get("barrier_check"),
            max_steps=24,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run(
            FixturePlanPlanner(
                journey["evaluation_config"]["planner"]["fallback"]
            ).actions()
        )

        assert result.outcome == "blocked"
        assert result.terminal_reason == "KEYBOARD_TARGET_NOT_REACHABLE"
        assert result.steps_completed == 5
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_planner_receives_one_bounded_observation_per_keyboard_turn(tmp_path: Path) -> None:
    server, thread, origin = _serve_fixture()
    try:
        journey = _load_manifest()["journeys"][0]
        run_id = uuid4()
        planner = RecordingPlanner(
            FixturePlanPlanner(journey["evaluation_config"]["planner"]["fallback"])
        )
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}{journey['start_path']}",
            allowed_origins=[origin],
            completion_policy=journey["completion_policy"],
            barrier_check=None,
            max_steps=24,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run_with_planner(planner, goal=journey["goal"])

        assert result.outcome == "completed"
        assert len(planner.observations) == result.steps_completed
        assert all(len(item.interactive_elements) <= 40 for item in planner.observations)
        assert all(len(item.visible_text) <= 4000 for item in planner.observations)
        assert all(len(item.history) <= 8 for item in planner.observations)
        assert all("<script" not in item.visible_text.lower() for item in planner.observations)
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_semantic_journey_without_test_ids_completes_from_url_and_heading(
    tmp_path: Path,
) -> None:
    server, thread, origin = _serve_semantic_journey()
    observations: list[PlannerObservationV1] = []
    try:
        run_id = uuid4()
        planner = RecordingPlanner(
            FixturePlanPlanner(
                {
                    "kind": "fixture_plan.v1",
                    "actions": [
                        {"action": "tab"},
                        {"action": "type", "value": "Web accessibility"},
                        {"action": "tab"},
                        {"action": "enter"},
                    ],
                }
            )
        )
        executor = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}/wiki/Main_Page",
            allowed_origins=[origin],
            completion_policy={
                "signals": [
                    {
                        "id": "url",
                        "type": "url_path_equals",
                        "expected": "/wiki/Web_accessibility",
                    },
                    {
                        "id": "heading",
                        "type": "element_present",
                        "locator": {
                            "by": "heading",
                            "value": "Web accessibility",
                            "level": 1,
                        },
                    },
                ]
            },
            barrier_check=None,
            max_steps=8,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        )

        executor_result = executor.run_with_planner(
            planner, goal="Find the Web accessibility article"
        )
        observations.extend(planner.observations)

        assert executor_result.outcome == "completed"
        search = next(
            element
            for observation in observations
            for element in observation.interactive_elements
            if element.name == "Search articles"
        )
        assert search.role == "searchbox"
        assert search.editable is True
        assert search.required is True
        assert search.test_id is None
        checkbox = next(
            element
            for observation in observations
            for element in observation.interactive_elements
            if element.name == "Remember choice"
        )
        assert checkbox.role == "checkbox"
        assert checkbox.editable is False
        assert executor.runtime_metadata["browser_engine"] == "chromium"
        assert executor.runtime_metadata["browser_version"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_semantic_completion_requires_the_expected_heading(tmp_path: Path) -> None:
    server, thread, origin = _serve_semantic_journey(article_heading="Different article")
    try:
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}/wiki/Main_Page",
            allowed_origins=[origin],
            completion_policy={
                "signals": [
                    {
                        "id": "url",
                        "type": "url_path_equals",
                        "expected": "/wiki/Web_accessibility",
                    },
                    {
                        "id": "heading",
                        "type": "element_present",
                        "locator": {
                            "by": "heading",
                            "value": "Web accessibility",
                            "level": 1,
                        },
                    },
                ]
            },
            barrier_check=None,
            max_steps=8,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run(
            [
                ProposedActionV1(action=ActionKind.TAB),
                ProposedActionV1(action=ActionKind.TYPE, value="Web accessibility"),
                ProposedActionV1(action=ActionKind.TAB),
                ProposedActionV1(action=ActionKind.ENTER),
            ]
        )

        assert result.outcome == "inconclusive"
        assert result.terminal_reason == "PLAN_COMPLETED_WITHOUT_VERIFIED_COMPLETION"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_repeated_focus_cycle_stops_before_the_full_action_budget(tmp_path: Path) -> None:
    server, thread, origin = _serve_semantic_journey(article_heading="Unreachable")
    try:
        run_id = uuid4()
        result = KeyboardExecutor(
            run_id=run_id,
            start_url=f"{origin}/wiki/Main_Page",
            allowed_origins=[origin],
            target_policy={
                "navigation_origins": [origin],
                "resource_origins": [origin],
                "navigation_path_prefixes": ["/wiki/"],
                "no_progress_limit": 3,
                "max_actions": 20,
            },
            completion_policy={
                "signals": [
                    {"id": "never", "type": "url_path_equals", "expected": "/never"}
                ]
            },
            barrier_check=None,
            max_steps=20,
            action_timeout_ms=5000,
            headless=True,
            browser_executable_path=os.environ.get("EVALUATOR_BROWSER_EXECUTABLE") or None,
            artifact_store=LocalArtifactStore(tmp_path, run_id),
            on_step=lambda step, artifacts: None,
        ).run([ProposedActionV1(action=ActionKind.TAB) for _ in range(20)])

        assert result.outcome == "agent_error"
        assert result.terminal_reason == "REPEATED_FOCUS_CYCLE"
        assert result.steps_completed < 20
    finally:
        server.shutdown()
        thread.join(timeout=2)
