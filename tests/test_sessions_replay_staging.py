"""Signed-in journeys, record and replay, staging writes and baselines."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from accesspath.cli import main
from accesspath.journey_file import JourneyFileV1, PlanStepV1, load_journey
from accesspath.recorder import capture_session, record_journey, steps_from_keys
from apps.journeys.models import Journey, JourneySession
from apps.runs.credentials import decrypt_session
from apps.runs.models import Finding, Run, RunStep
from apps.runs.report import build_report
from apps.runs.services import _saved_session, _target_policy
from engine.artifacts import LocalArtifactStore
from engine.contracts import ActionKind, ProposedActionV1, TargetPolicyV1
from engine.executor import KeyboardExecutor
from engine.fixture_site import serve_directory
from engine.session_state import SessionStateError, limit_to_origins, parse_storage_state
from engine.target_policy import TargetPolicy

ROOT = Path(__file__).resolve().parents[1]

SIGNED_IN_PAGE = """<!doctype html><html lang="en"><head><title>Account</title></head><body>
<main><h1 id="greeting">Please sign in</h1><a href="/orders.html">Orders</a></main>
<script>if (document.cookie.includes('auth=1'))
  document.getElementById('greeting').textContent = 'Welcome back';</script></body></html>"""


# Saved sessions -------------------------------------------------------------------


def test_session_state_is_limited_to_the_journeys_own_sites() -> None:
    state = {
        "cookies": [
            {"name": "a", "value": "1", "domain": ".shop.example", "path": "/"},
            {"name": "b", "value": "2", "domain": "tracker.example", "path": "/"},
        ],
        "origins": [
            {"origin": "https://www.shop.example", "localStorage": []},
            {"origin": "https://evil.example", "localStorage": []},
        ],
    }
    limited = limit_to_origins(state, ["https://www.shop.example"])
    assert [cookie["name"] for cookie in limited["cookies"]] == ["a"]
    assert [entry["origin"] for entry in limited["origins"]] == ["https://www.shop.example"]
    for bad in (b"not json", b"[]", json.dumps({"cookies": "x"}).encode(), b"x" * 1_000_001):
        with pytest.raises(SessionStateError):
            parse_storage_state(bad)


def test_cli_signs_in_with_a_saved_session(tmp_path: Path) -> None:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(SIGNED_IN_PAGE, encoding="utf-8")
    session_file = tmp_path / "session.json"
    with serve_directory(site) as origin:
        capture_session(
            f"{origin}/index.html",
            session_file,
            headless=True,
            wait=lambda page: page.evaluate("document.cookie = 'auth=1; path=/'"),
        )
    assert "auth" in session_file.read_text()
    journey = tmp_path / "journey.json"
    journey.write_text(
        json.dumps(
            {
                "name": "Account greeting",
                "goal": "Open the account page while signed in.",
                "site_dir": "site",
                "start_path": "/index.html",
                "success": {"text_present": "Welcome back"},
                "plan": [{"action": "tab", "purpose": "move to the first link"}],
            }
        )
    )
    signed_in = main(
        [
            "run",
            str(journey),
            "--session",
            str(session_file),
            "--out",
            str(tmp_path / "a"),
            "--format",
            "json",
        ]
    )
    signed_out = main(["run", str(journey), "--out", str(tmp_path / "b"), "--format", "json"])
    assert signed_in == 0
    assert signed_out == 3  # never reaches the signed-in greeting: incomplete, site not blamed


@pytest.mark.django_db
def test_sessions_are_encrypted_owner_only_and_used_only_by_the_owner(
    client, user, django_user_model
) -> None:
    journey = Journey.objects.create(
        name="Shop account",
        goal="Open the orders page by keyboard.",
        start_url="https://www.shop.example/",
        allowed_origins=["https://www.shop.example"],
        completion_policy={},
        evaluation_config={"source": "user"},
    )
    state = {
        "cookies": [
            {"name": "sid", "value": "secret-cookie", "domain": "www.shop.example", "path": "/"}
        ],
        "origins": [],
    }
    upload = SimpleUploadedFile("s.json", json.dumps(state).encode(), "application/json")
    client.post(reverse("runs:save_session", args=[journey.pk]), {"state": upload})
    session = JourneySession.objects.get(journey=journey)
    assert "secret-cookie" not in session.encrypted_state
    assert "secret-cookie" in decrypt_session(session.encrypted_state)
    page = client.get(reverse("runs:journey_settings", args=[journey.pk])).content.decode()
    assert "1 cookies for www.shop.example" in page and "secret-cookie" not in page

    mine = Run.objects.create(
        journey=journey, planner_provider="fixture", planner_metadata={"started_by": user.pk}
    )
    other_user = django_user_model.objects.create_user("other", password="x-horse-battery")
    theirs = Run.objects.create(
        journey=journey, planner_provider="fixture", planner_metadata={"started_by": other_user.pk}
    )
    used, note = _saved_session(mine)
    assert used["cookies"][0]["value"] == "secret-cookie" and note.startswith("Signed in")
    assert _saved_session(theirs) == (
        None,
        "A saved sign-in exists, but only runs its owner starts use it.",
    )

    from django.test import Client

    stranger = Client()
    stranger.force_login(other_user)
    # Staging writes and replay plans run under the owner's sign-in: only the owner
    # may change them.
    stranger.post(
        reverse("runs:save_staging", args=[journey.pk]),
        {"enable": "on", "confirm": "on", "max_writes": "20"},
    )
    journey.refresh_from_db()
    assert "staging" not in journey.evaluation_config
    stranger.post(reverse("runs:save_replay", args=[journey.pk]), {"run_id": str(mine.id)})
    journey.refresh_from_db()
    assert "recorded_plan" not in journey.evaluation_config
    # ...and if staging was turned on by someone else, the sign-in is not used.
    journey.evaluation_config = {
        **journey.evaluation_config,
        "staging": {"enabled": True, "confirmed_by": "other"},
    }
    journey.save()
    mine.refresh_from_db()
    assert _saved_session(mine)[0] is None
    journey.evaluation_config = {"source": "user"}
    journey.save()
    # A bad run id is a 404, not a server error.
    assert (
        client.post(reverse("runs:save_baseline", args=[journey.pk]), {"run_id": "abc"}).status_code
        == 404
    )
    # Pages seen while signed in are visible only to the person who started the run.
    mine.planner_metadata = {"started_by": user.pk, "signed_in": True}
    mine.save()
    from django.conf import settings

    shot = Path(settings.MEDIA_ROOT) / "runs" / str(mine.id) / "step-01-after.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(b"png")
    try:
        evidence = f"/evidence/runs/{mine.id}/step-01-after.png"
        assert stranger.get(reverse("runs:detail", args=[mine.id])).status_code == 404
        assert stranger.get(reverse("runs:report_json", args=[mine.id])).status_code == 404
        assert stranger.get(evidence).status_code == 404
        assert client.get(reverse("runs:detail", args=[mine.id])).status_code == 200
        assert client.get(evidence).status_code == 200
    finally:
        shot.unlink()
    stranger.post(reverse("runs:save_session", args=[journey.pk]), {"remove": "1"})
    assert JourneySession.objects.filter(journey=journey).exists()
    client.post(reverse("runs:save_session", args=[journey.pk]), {"remove": "1"})
    assert not JourneySession.objects.filter(journey=journey).exists()


# Record and replay ----------------------------------------------------------------


def test_recorded_keys_become_plan_steps() -> None:
    events = [
        {"key": "Tab"},
        {"key": "Tab", "shift": True},
        {"key": "Enter", "name": "Search"},
        {"key": "h", "editable": True},
        {"key": "x", "editable": True},
        {"key": "Backspace", "editable": True},
        {"key": "i", "editable": True},
        {"key": " ", "editable": True},
        {"key": "!", "editable": True},
        {"key": "Shift"},
        {"key": "Escape"},
    ]
    steps = steps_from_keys(events)
    assert [(step.action, step.value) for step in steps] == [
        (ActionKind.TAB, None),
        (ActionKind.SHIFT_TAB, None),
        (ActionKind.ENTER, None),
        (ActionKind.TYPE, "hi !"),
        (ActionKind.ESCAPE, None),
    ]


def test_recording_keeps_final_field_values_and_skips_passwords(tmp_path: Path) -> None:
    from tests.page_server import serve_pages

    pages = {
        "/": (
            "<main><label>Search <input id=q></label>"
            "<label>Password <input id=p type=password></label>"
            "<a href=/done>Go</a></main>"
        ),
        "/done": "<main><h1>Done</h1></main>",
    }

    def drive(page) -> None:
        page.keyboard.press("Tab")
        page.keyboard.type("abc")
        page.keyboard.press("ArrowLeft")
        page.keyboard.type("X")
        page.keyboard.press("Tab")
        page.keyboard.type("hunter2-S3cret")
        page.keyboard.press("Tab")
        page.keyboard.press("Enter")
        page.wait_for_url("**/done")

    out = tmp_path / "rec.json"
    with serve_pages(pages) as origin:
        record_journey(
            f"{origin}/", out, name="Rec", goal="Reach done.", headless=True, drive=drive
        )
    text = out.read_text()
    assert "hunter2" not in text
    journey = load_journey(out)
    typed = [step.value for step in journey.plan if step.action == ActionKind.TYPE]
    assert typed == ["abXc"]
    assert journey.success.url_contains == "/done"
    assert any(step.target_hint == "Go" for step in journey.plan)


def test_record_a_journey_then_replay_it_without_ai(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "fixtures/clinic/journey-manifest.json").read_text())
    accessible = next(
        item for item in manifest["journeys"] if item["key"] == "clinic-accessible-booking"
    )
    plan = accessible["evaluation_config"]["planner"]["fallback"]
    keys = {
        "tab": "Tab",
        "shift_tab": "Shift+Tab",
        "enter": "Enter",
        "space": " ",
        "escape": "Escape",
        "arrow_down": "ArrowDown",
        "arrow_up": "ArrowUp",
    }

    def drive(page) -> None:
        for step in plan["actions"]:
            if step["action"] == "type":
                page.keyboard.press("Control+A")
                page.keyboard.type(step["value"].format(**plan.get("synthetic_values", {})))
            else:
                page.keyboard.press(keys[step["action"]])
            page.wait_for_timeout(150)

    out = tmp_path / "recorded.json"
    with serve_directory(ROOT / "fixtures/clinic") as origin:
        record_journey(
            f"{origin}/accessible/index.html",
            out,
            name="Recorded booking",
            goal="Book an appointment by keyboard.",
            headless=True,
            drive=drive,
        )
    recorded = load_journey(out)
    assert recorded.plan and recorded.success.url_contains
    # Replay on the folder instead of the (now closed) recording server.
    data = json.loads(out.read_text())
    data.pop("start_url")
    data.update({"site_dir": str(ROOT / "fixtures/clinic"), "start_path": "/accessible/index.html"})
    out.write_text(json.dumps(data))
    assert main(["run", str(out), "--out", str(tmp_path / "replay"), "--format", "json"]) == 0


@pytest.mark.django_db
def test_save_a_completed_run_as_the_replay_plan_and_export_it(client) -> None:
    journey = Journey.objects.create(
        name="Wiki search",
        goal="Find the article by keyboard.",
        start_url="https://en.wikipedia.org/wiki/Main_Page",
        allowed_origins=["https://en.wikipedia.org"],
        completion_policy={"signals": [{"id": "s", "type": "url_contains", "expected": "/wiki/W"}]},
        evaluation_config={
            "source": "user",
            "planner": {
                "kind": "gemini.v1",
                "allow_no_fallback": True,
                "synthetic_values": {"text_to_type": "Web accessibility"},
            },
        },
    )
    assert not journey.has_fixture_plan
    run = Run.objects.create(
        journey=journey, planner_provider="groq", status="succeeded", outcome="completed"
    )
    for number, action in enumerate(
        [{"action": "tab"}, {"action": "type", "value": "Web accessibility"}, {"action": "enter"}],
        start=1,
    ):
        RunStep.objects.create(run=run, step_number=number, evidence={"executed_action": action})
    RunStep.objects.create(run=run, step_number=4, evidence={"executed_action": None})
    client.post(reverse("runs:save_replay", args=[journey.pk]), {"run_id": str(run.id)})
    journey.refresh_from_db()
    assert journey.has_fixture_plan
    fallback = journey.evaluation_config["planner"]["fallback"]
    assert [step["action"] for step in fallback["actions"]] == ["tab", "type", "enter"]
    assert journey.evaluation_config["recorded_plan"]["steps"] == 3

    exported = client.get(reverse("runs:journey_file", args=[journey.pk]))
    data = json.loads(exported.content)
    assert JourneyFileV1.model_validate(data).plan[1].value == "Web accessibility"

    call_command("seed_fixture_journeys", stdout=StringIO())
    seeded = Journey.objects.get(evaluation_config__journey_key="bench-no-focus-style")
    before = dict(seeded.evaluation_config)
    client.post(reverse("runs:save_replay", args=[seeded.pk]), {"run_id": str(run.id)})
    seeded.refresh_from_db()
    assert seeded.evaluation_config == before  # reviewed plans are never replaced


# Staging writes -------------------------------------------------------------------


def _policy(**extra) -> dict:
    return {
        "navigation_origins": ["http://a.test"],
        "resource_origins": ["http://a.test"],
        "navigation_path_prefixes": ["/"],
        **extra,
    }


def test_staging_writes_are_bounded_by_policy() -> None:
    with pytest.raises(ValueError):
        TargetPolicyV1.model_validate(_policy(allowed_methods=["GET", "POST"]))
    with pytest.raises(ValueError):
        TargetPolicyV1.model_validate(
            _policy(allowed_methods=["GET", "POST"], write_origins=["http://b.test"], max_writes=2)
        )
    policy = TargetPolicy(
        TargetPolicyV1.model_validate(
            _policy(allowed_methods=["GET", "POST"], write_origins=["http://a.test"], max_writes=1)
        )
    )
    assert policy.decide_request("http://a.test/x", method="POST", is_navigation=True).allowed
    assert policy.decide_request("http://a.test/x", method="POST", is_navigation=True).code == (
        "WRITE_BUDGET_EXCEEDED"
    )
    read_only = TargetPolicy(TargetPolicyV1.model_validate(_policy()))
    assert not read_only.decide_request(
        "http://a.test/x", method="POST", is_navigation=True
    ).allowed


class _FormSite(BaseHTTPRequestHandler):
    page = (
        "<!doctype html><html lang='en'><head><title>Sign up</title></head><body><main>"
        "<form method='post' action='/thanks'><label>Email <input name='email'></label>"
        "<button>Sign up</button></form></main></body></html>"
    )

    def do_GET(self) -> None:  # noqa: N802
        self._send(self.page)

    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._send(
            "<!doctype html><html lang='en'><head><title>Thanks</title></head>"
            "<body><main><h1>Thanks for signing up</h1></main></body></html>"
        )

    def _send(self, html: str) -> None:
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        return


def _signup(tmp_path: Path, origin: str, policy: dict):
    keys = [
        ProposedActionV1(action=ActionKind.TAB),
        ProposedActionV1(action=ActionKind.TYPE, value="test@example.org"),
        ProposedActionV1(action=ActionKind.TAB),
        ProposedActionV1(action=ActionKind.ENTER),
    ]
    run_id = uuid4()
    return KeyboardExecutor(
        run_id=run_id,
        start_url=f"{origin}/",
        allowed_origins=[origin],
        target_policy=policy,
        completion_policy={
            "signals": [{"id": "t", "type": "text_present", "expected": "Thanks for signing up"}]
        },
        barrier_check=None,
        max_steps=8,
        action_timeout_ms=5000,
        headless=True,
        artifact_store=LocalArtifactStore(tmp_path, run_id),
        on_step=lambda *args: None,
    ).run(keys)


def test_a_staging_journey_can_submit_a_form_and_a_read_only_one_cannot(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FormSite)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        base = {
            "navigation_origins": [origin],
            "resource_origins": [origin],
            "navigation_path_prefixes": ["/"],
        }
        staging = _signup(
            tmp_path / "s",
            origin,
            {
                **base,
                "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST"],
                "write_origins": [origin],
                "max_writes": 2,
            },
        )
        read_only = _signup(tmp_path / "r", origin, base)
    finally:
        server.shutdown()
    assert staging.outcome == "completed"
    assert read_only.outcome == "safety_stopped"


def test_a_staging_write_cannot_be_redirected_to_another_site(tmp_path: Path) -> None:
    received: list[tuple[str, str]] = []

    class Elsewhere(_FormSite):
        def do_POST(self) -> None:  # noqa: N802
            received.append(("POST", self.path))
            super().do_POST()

    other = ThreadingHTTPServer(("127.0.0.1", 0), Elsewhere)
    threading.Thread(target=other.serve_forever, daemon=True).start()
    elsewhere = f"http://127.0.0.1:{other.server_port}"

    def redirecting(status: int, location: str):
        class Redirecting(_FormSite):
            def do_POST(self) -> None:  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/thanks":
                    self.send_response(status)
                    self.send_header("Location", location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                super().do_POST()

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/done":
                    self._send("<main><h1>Thanks for signing up</h1></main>")
                    return
                super().do_GET()

        return Redirecting

    outcomes = {}
    for label, status, location in (
        ("307 elsewhere", 307, f"{elsewhere}/steal"),
        ("302 elsewhere", 302, f"{elsewhere}/steal"),
        ("303 same site", 303, "/done"),
    ):
        server = ThreadingHTTPServer(("127.0.0.1", 0), redirecting(status, location))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{server.server_port}"
        try:
            result = _signup(
                tmp_path / str(status),
                origin,
                {
                    "navigation_origins": [origin],
                    "resource_origins": [origin],
                    "navigation_path_prefixes": ["/"],
                    "allowed_methods": ["GET", "HEAD", "OPTIONS", "POST"],
                    "write_origins": [origin],
                    "max_writes": 2,
                },
            )
        finally:
            server.shutdown()
        outcomes[label] = result.outcome
    other.shutdown()
    assert received == []
    assert outcomes == {
        "307 elsewhere": "safety_stopped",
        "302 elsewhere": "safety_stopped",
        "303 same site": "completed",
    }


def test_staging_writes_respect_paths_and_background_posts_do_not_stop_the_run() -> None:
    policy = TargetPolicy(
        TargetPolicyV1.model_validate(
            _policy(
                allowed_methods=["GET", "POST"],
                write_origins=["http://a.test"],
                max_writes=1,
                navigation_path_prefixes=["/shop/"],
            )
        )
    )
    outside = policy.decide_request("http://a.test/admin/delete", method="POST", is_navigation=True)
    assert (outside.allowed, outside.code) == (False, "WRITE_PATH_NOT_ALLOWED")
    assert policy.decide_request("http://a.test/shop/x", method="POST", is_navigation=False).allowed
    beacon = policy.decide_request("http://a.test/shop/y", method="POST", is_navigation=False)
    assert (beacon.allowed, beacon.fatal) == (False, False)


@pytest.mark.django_db
def test_staging_needs_confirmation_and_only_applies_to_added_sites(client) -> None:
    journey = Journey.objects.create(
        name="Staging sign-up",
        goal="Sign up on staging by keyboard.",
        start_url="https://staging.shop.example/signup",
        allowed_origins=["https://staging.shop.example"],
        completion_policy={},
        evaluation_config={
            "source": "user",
            "target_policy": {
                "navigation_origins": ["https://staging.shop.example"],
                "resource_origins": ["https://staging.shop.example"],
                "navigation_path_prefixes": ["/"],
            },
        },
    )
    url = reverse("runs:save_staging", args=[journey.pk])
    client.post(url, {"enable": "on", "max_writes": "3"})
    journey.refresh_from_db()
    assert "staging" not in journey.evaluation_config
    client.post(url, {"enable": "on", "max_writes": "3", "confirm": "on"})
    journey.refresh_from_db()
    policy, writes = _target_policy(journey)
    assert writes == 3 and policy["write_origins"] == ["https://staging.shop.example"]
    TargetPolicyV1.model_validate(policy)
    client.post(url, {})
    journey.refresh_from_db()
    assert _target_policy(journey)[1] == 0

    call_command("seed_fixture_journeys", stdout=StringIO())
    demo = Journey.objects.get(evaluation_config__journey_key="clinic-accessible-booking")
    client.post(reverse("runs:save_staging", args=[demo.pk]), {"enable": "on", "confirm": "on"})
    demo.refresh_from_db()
    assert "staging" not in demo.evaluation_config


# Baselines ------------------------------------------------------------------------


@pytest.mark.django_db
def test_reports_compare_with_the_baseline(client) -> None:
    journey = Journey.objects.create(
        name="Library",
        goal="Apply for a card by keyboard.",
        start_url="http://127.0.0.1:8001/x",
        allowed_origins=["http://127.0.0.1:8001"],
        completion_policy={},
        evaluation_config={},
    )

    def make_run(*finding_ids: str) -> Run:
        run = Run.objects.create(
            journey=journey, planner_provider="fixture", status="succeeded", outcome="completed"
        )
        for finding_id in finding_ids:
            Finding.objects.create(
                run=run,
                finding_id=finding_id,
                rule_id="bypass-blocks",
                severity="moderate",
                status="confirmed",
                title=f"T{finding_id}",
                summary="s",
                url="http://127.0.0.1:8001/x",
            )
        return run

    old = make_run("a" * 16, "b" * 16)
    new = make_run("a" * 16, "c" * 16)
    client.post(reverse("runs:save_baseline", args=[journey.pk]), {"run_id": str(old.id)})
    report = build_report(Run.objects.get(pk=new.pk))
    assert report["baseline"]["new"] == 1 and report["baseline"]["fixed"] == ["T" + "b" * 16]
    flags = {row["id"]: row.get("baseline_new") for row in report["findings"]}
    assert flags == {"a" * 16: False, "c" * 16: True}
    page = client.get(reverse("runs:detail", args=[new.id])).content.decode()
    assert "New since baseline" in page and "1 new · 1 fixed" in page
    # The baseline itself compares with nothing.
    assert build_report(Run.objects.get(pk=old.pk))["baseline"] is None
    assert PlanStepV1(action="tab").action == ActionKind.TAB
