"""Regression tests for the October security review of the code side."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.codebase.models import RepoBinding, RepoStatus
from apps.journeys.models import Journey
from apps.runs.models import Finding, Run
from apps.runs.report import build_report
from engine.code_index import build_index
from engine.code_locator import SourceReader, _match_source_hint
from engine.repo_clone import RepoCloneError, clone_snapshot, validate_repo_url

PEM = "\n".join(
    ["const key = `-----BEGIN RSA PRIVATE KEY-----"]
    + ["MIIEpAIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun" for _ in range(8)]
    + ["-----END RSA PRIVATE KEY-----`;", "export default key;"]
)


@pytest.fixture
def other_user(db, django_user_model):
    return django_user_model.objects.create_user("someone-else", password="another horse battery")


def _journey(name: str = "Clinic", **extra) -> Journey:
    return Journey.objects.create(
        name=name, goal="Book an appointment by keyboard.", start_url="http://127.0.0.1:8001/broken/",
        allowed_origins=["http://127.0.0.1:8001"], completion_policy={}, evaluation_config={}, **extra,
    )


@pytest.mark.django_db
def test_adding_a_repo_never_takes_over_another_persons_journey(client, other_user) -> None:
    theirs = RepoBinding.objects.create(owner=other_user, repo_url="https://github.com/them/site")
    journey = _journey(repo_binding=theirs)
    free = _journey("Free clinic")
    with patch("apps.codebase.views._queue"):
        client.post(
            reverse("codebase:add"),
            {"repo_url": "https://github.com/me/site", "live_site_url": "http://127.0.0.1:8001/"},
        )
    journey.refresh_from_db()
    free.refresh_from_db()
    assert journey.repo_binding_id == theirs.pk
    assert free.repo_binding is not None and free.repo_binding.owner.username == "tester"


@pytest.mark.django_db
def test_code_locations_are_shown_only_to_the_repository_owner(client, user, other_user) -> None:
    binding = RepoBinding.objects.create(owner=user, repo_url="https://github.com/me/private",
                                         status=RepoStatus.READY)
    run = Run.objects.create(journey=_journey(repo_binding=binding), planner_provider="fixture",
                             status="succeeded", outcome="blocked")
    Finding.objects.create(
        run=run, finding_id="f" * 16, rule_id="keyboard-operable", severity="critical", status="confirmed",
        title="t", summary="s", url="http://127.0.0.1:8001/",
        data={"locations": {"exact": [{"path": "src/secret.js", "line": 3, "snippet": "PRIVATE-CODE"}],
                            "fix": {"path": "src/secret.js", "patch": "PRIVATE-PATCH"}}},
    )
    assert build_report(run, user)["findings"][0]["locations"]
    assert build_report(run, other_user)["findings"][0]["locations"] is None
    assert build_report(run)["findings"][0]["locations"] is None

    stranger = Client()
    stranger.force_login(other_user)
    for name in ("runs:detail", "runs:report_json", "runs:report_html"):
        body = stranger.get(reverse(name, kwargs={"run_id": run.id})).content.decode()
        assert "PRIVATE-CODE" not in body and "PRIVATE-PATCH" not in body
    assert "PRIVATE-PATCH" in client.get(reverse("runs:report_json", kwargs={"run_id": run.id})).content.decode()

    response = stranger.post(reverse("runs:map_code", kwargs={"run_id": run.id}))
    assert response.status_code == 302
    finding = Finding.objects.get()
    finding.data = {"locations": {"fix": {"path": "fixtures/clinic/broken/slots.html", "edits": {"6": "x"}}}}
    finding.save()
    stranger.post(reverse("runs:verify_fix", args=[finding.pk]))
    finding.refresh_from_db()
    assert "verification" not in finding.data["locations"]


def test_secrets_spanning_lines_are_redacted_without_moving_line_numbers(tmp_path: Path) -> None:
    (tmp_path / "key.js").write_text(PEM + "\n", encoding="utf-8")
    reader = SourceReader(tmp_path, {"files": [{"path": "key.js"}]})
    lines = reader.lines("key.js")
    assert len(lines) == len(PEM.splitlines())
    assert lines[-1] == "export default key;"
    assert "MIIEp" not in "\n".join(lines)
    assert reader.search("MIIEp") == []
    assert "MIIEp" not in reader.snippet("key.js", 4)


def test_index_snippets_are_redacted(tmp_path: Path) -> None:
    (tmp_path / "App.jsx").write_text(
        '<div tabIndex="-1" data-key="AKIAABCDEFGHIJKLMNOP" onClick={go}>ghp_abcdefghijklmnopqrstuvwxyz0123456789</div>\n',
        encoding="utf-8",
    )
    snippets = " ".join(item["snippet"] for item in build_index(tmp_path).patterns)
    assert snippets, "the tabindex pattern should be indexed"
    assert "AKIAABCDEFGHIJKLMNOP" not in snippets and "ghp_abcdef" not in snippets


@pytest.mark.parametrize("url", ["https://github.com:abc/a/b", "https://github.com:99999/a/b"])
def test_bad_ports_are_a_plain_error(url: str) -> None:
    with pytest.raises(RepoCloneError):
        validate_repo_url(url, ("github.com",))


def test_page_supplied_line_numbers_are_clamped(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.jsx").write_text("a\nb\nc\n", encoding="utf-8")
    reader = SourceReader(tmp_path, {"files": [{"path": "src/App.jsx"}]})
    for value, expected in (("0", 1), ("-5", 1), ("abc", 1), ("999", 3), ("2", 2)):
        element = {"source_file": "/build/src/App.jsx", "source_line": value}
        assert _match_source_hint(element, reader).line == expected


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def test_oversized_trees_are_refused_before_checkout(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _git("init", "-q", "-b", "main", cwd=source)
    (source / "big.txt").write_text("x" * 50_000, encoding="utf-8")
    (source / "index.html").write_text("<button>ok</button>\n", encoding="utf-8")
    _git("add", ".", cwd=source)
    _git("commit", "-q", "-m", "init", cwd=source)
    url = source.as_uri()
    with pytest.raises(RepoCloneError, match="too large"):
        clone_snapshot(url, tmp_path / "out", max_bytes=10_000, allow_file_urls=True)
    assert not (tmp_path / "out").exists()
    snapshot = clone_snapshot(url, tmp_path / "ok", allow_file_urls=True)
    assert snapshot.file_count == 2 and (tmp_path / "ok" / "index.html").is_file()
    assert not (tmp_path / "ok" / ".git").exists()


@pytest.mark.django_db
def test_ai_code_search_only_runs_for_the_repository_owner(user, other_user) -> None:
    from apps.runs.services import started_by_repo_owner

    binding = RepoBinding.objects.create(owner=user, repo_url="https://github.com/me/private")
    journey = _journey(repo_binding=binding)
    mine = Run.objects.create(journey=journey, planner_provider="groq", planner_metadata={"started_by": user.pk})
    theirs = Run.objects.create(journey=journey, planner_provider="groq",
                                planner_metadata={"started_by": other_user.pk})
    unknown = Run.objects.create(journey=journey, planner_provider="groq")
    assert started_by_repo_owner(mine)
    assert not started_by_repo_owner(theirs) and not started_by_repo_owner(unknown)
