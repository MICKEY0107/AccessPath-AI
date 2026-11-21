"""The parts that make AccessPath easy to try: demo, status, getting started."""

from __future__ import annotations

import socket
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.codebase.models import RepoBinding, RepoSource
from apps.journeys.models import Journey
from apps.runs.models import Run
from engine.fixture_site import is_reachable, serve_if_missing

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_fixture_fallback_serves_only_the_bundled_site() -> None:
    origin = f"http://127.0.0.1:{_free_port()}"
    assert not is_reachable(origin)
    with serve_if_missing(origin, ROOT / "fixtures" / "clinic") as serving:
        assert serving and is_reachable(origin)
        page = urlopen(f"{origin}/accessible/index.html", timeout=5).read().decode()
        assert "Clinic" in page or "clinic" in page
        for path in ("/", "/.git/config", "/../manage.py"):
            with pytest.raises(HTTPError):
                urlopen(f"{origin}{path}", timeout=5)
    assert not is_reachable(origin)
    # Something else already answers there: AccessPath never starts its own server.
    with serve_if_missing(origin, ROOT / "fixtures" / "clinic") as outer:
        assert outer
        import engine.fixture_site as fixture_site

        saved = dict(fixture_site._SERVERS)
        fixture_site._SERVERS.clear()  # pretend the running server belongs to someone else
        try:
            with serve_if_missing(origin, ROOT / "fixtures" / "clinic") as foreign:
                assert not foreign
        finally:
            fixture_site._SERVERS.update(saved)
    with serve_if_missing("https://example.org", ROOT / "fixtures" / "clinic") as remote:
        assert not remote  # only loopback http origins


@pytest.mark.django_db
def test_home_checklist_and_load_demo(client, user, settings, tmp_path) -> None:
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    settings.GROQ_API_KEY = ""
    settings.GEMINI_API_KEY = ""
    settings.OPENROUTER_API_KEY = ""
    settings.OLLAMA_BASE_URL = ""
    page = client.get(reverse("core:home")).content.decode()
    assert "0 of 5 done" in page and "Load the demo" in page
    response = client.post(reverse("core:load_demo"))
    assert response.status_code == 302
    binding = RepoBinding.objects.get(owner=user)
    assert binding.source == RepoSource.BUNDLED and binding.status == "ready"
    assert (binding.source_dir / "fixtures" / "clinic" / "broken" / "slots.html").is_file()
    assert Journey.objects.filter(repo_binding=binding).count() == 12
    page = client.get(reverse("core:home")).content.decode()
    assert "2 of 5 done" in page and "Reload demo" in page


def test_install_axe_core_uses_a_non_conflicting_version_option(
    settings, tmp_path, monkeypatch
) -> None:
    from apps.runs.management.commands import install_axe_core

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"/*! axe v4.10.3 */\nwindow.axe = {};"

    settings.AXE_CORE_PATH = tmp_path / "axe.min.js"
    monkeypatch.setattr(install_axe_core, "urlopen", lambda *args, **kwargs: Response())
    output = StringIO()
    call_command("install_axe_core", "--axe-version", "4.10.3", stdout=output)
    assert settings.AXE_CORE_PATH.is_file()
    assert "Saved axe-core 4.10.3" in output.getvalue()


@pytest.mark.django_db
def test_code_page_offers_the_demo_repository_once(client, user, settings, tmp_path) -> None:
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    call_command("seed_fixture_journeys", stdout=StringIO())
    assert "Use the demo repository" in client.get(reverse("codebase:page")).content.decode()
    client.post(reverse("codebase:demo"))
    page = client.get(reverse("codebase:page")).content.decode()
    assert "Demo copy" in page and "Use the demo repository" not in page
    binding = RepoBinding.objects.get(owner=user)
    (binding.source_dir / "fixtures" / "clinic" / "styles.css").unlink()
    client.post(reverse("codebase:analyze", args=[binding.pk]))  # re-copies, no worker needed
    assert (binding.source_dir / "fixtures" / "clinic" / "styles.css").is_file()


@pytest.mark.django_db
def test_status_page_and_check_setup(client) -> None:
    page = client.get(reverse("core:status")).content.decode()
    for label in (
        "Database",
        "Worker",
        "Browser",
        "Demo site",
        "axe-core",
        "Groq",
        "Local Ollama",
        "Secret key",
    ):
        assert label in page
    assert "sk-" not in page
    out = StringIO()
    call_command("check_setup", stdout=out)
    text = out.getvalue()
    assert "Database: Connected" in text and "Worker:" in text


@pytest.mark.django_db
def test_demo_setup_builds_a_working_demo(settings, tmp_path) -> None:
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    settings.MEDIA_ROOT = tmp_path / "output"
    settings.FIXTURE_ALLOWED_ORIGINS = (f"http://127.0.0.1:{_free_port()}",)
    # Public journeys reach live sites, so the demo never counts or runs them.
    call_command("seed_public_journeys", stdout=StringIO())
    out = StringIO()
    call_command("demo_setup", "--password", "demo-pass-1", "--runs", "none", stdout=out)
    assert "The demo is ready." in out.getvalue() and "demo-pass-1" in out.getvalue()
    assert "Journeys: 12 demo journeys" in out.getvalue()
    library = Journey.objects.get(evaluation_config__journey_key="bench-nav-no-skip")
    assert library.rule_config["custom"][0]["id"] == "custom-apply-button-reached-quickly"

    # A scripted run of the broken clinic: nothing serves the demo site, so the run
    # serves it itself, and the finding maps to the demo repository's exact line.
    from apps.runs.services import execute_configured_run

    broken = Journey.objects.get(evaluation_config__journey_key="clinic-keyboard-trap-control")
    owner = RepoBinding.objects.get().owner
    run = Run.objects.create(
        journey=broken, planner_provider="fixture", planner_metadata={"started_by": owner.pk}
    )
    execute_configured_run(run)
    run.refresh_from_db()
    assert run.outcome == "blocked"
    finding = run.findings.get(rule_id="keyboard-operable")
    exact = finding.data["locations"]["exact"][0]
    assert exact["path"] == "fixtures/clinic/broken/slots.html" and exact["line"] == 6

    again = StringIO()
    call_command("demo_setup", "--runs", "none", stdout=again)  # safe to repeat
    assert "Password: unchanged" in again.getvalue()
    assert RepoBinding.objects.count() == 1
    assert len(library.__class__.objects.get(pk=library.pk).rule_config["custom"]) == 1


def test_fallback_server_refuses_encoded_hidden_paths_and_is_shared(tmp_path) -> None:
    root = tmp_path / "site"
    (root / ".secret").mkdir(parents=True)
    (root / ".secret" / "x.txt").write_text("hidden", encoding="utf-8")
    (root / "page.html").write_text("<p>ok</p>", encoding="utf-8")
    origin = f"http://127.0.0.1:{_free_port()}"
    with serve_if_missing(origin, root) as first:
        assert first
        for path in (
            "/.secret/x.txt",
            "/%2Esecret/x.txt",
            "/%2esecret/x.txt",
            "/..%2f..%2fetc/passwd",
        ):
            with pytest.raises(HTTPError):
                urlopen(f"{origin}{path}", timeout=5)
        with serve_if_missing(origin, root) as second:
            assert second  # the same process shares its server
        assert urlopen(f"{origin}/page.html", timeout=5).read() == b"<p>ok</p>"  # still up
    assert not is_reachable(origin)


@pytest.mark.django_db
def test_load_demo_never_rewrites_existing_journeys_for_non_staff(
    client, settings, tmp_path
) -> None:
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    call_command("seed_fixture_journeys", stdout=StringIO())
    journey = Journey.objects.get(evaluation_config__journey_key="clinic-accessible-booking")
    Journey.objects.filter(pk=journey.pk).update(is_active=False, goal="Edited by an admin.")
    client.post(reverse("core:load_demo"))
    journey.refresh_from_db()
    assert journey.goal == "Edited by an admin." and journey.is_active is False


@pytest.mark.django_db
def test_demo_never_takes_journeys_linked_elsewhere(
    client, user, django_user_model, settings, tmp_path
) -> None:
    settings.REPO_STORAGE_ROOT = tmp_path / "repos"
    call_command("seed_fixture_journeys", stdout=StringIO())
    own = RepoBinding.objects.create(
        owner=user, repo_url="https://github.com/me/site", status="ready"
    )
    mine = Journey.objects.get(evaluation_config__journey_key="clinic-accessible-booking")
    mine.repo_binding = own
    mine.save()
    client.post(reverse("codebase:demo"))
    client.post(reverse("codebase:demo"))  # twice: still one demo copy
    mine.refresh_from_db()
    assert mine.repo_binding_id == own.pk
    assert RepoBinding.objects.filter(owner=user, source=RepoSource.BUNDLED).count() == 1
    other = django_user_model.objects.create_user("second", password="another horse battery")
    from apps.codebase.demo import ensure_demo_binding

    binding, linked = ensure_demo_binding(other)
    assert binding.status == "ready" and linked == 0
