"""The `accesspath` command line: runs, reports, SARIF, baselines and PR comments."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from accesspath.cli import main
from accesspath.github import GitHubError, upsert_pr_comment
from accesspath.journey_file import JourneyFileV1, load_journey
from accesspath.report import COMMENT_MARKER

ROOT = Path(__file__).resolve().parents[1]
JOURNEYS = ROOT / "journeys"


def test_a_blocked_journey_exits_2_and_points_at_the_code(tmp_path: Path, capsys) -> None:
    code = main(
        ["run", str(JOURNEYS / "clinic-broken.json"), "--repo", str(ROOT), "--out", str(tmp_path)]
    )
    assert code == 2
    assert "Blocked" in capsys.readouterr().out
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["verdict"]["key"] == "blocked" and report["exit_code"] == 2
    sarif = json.loads((tmp_path / "results.sarif").read_text())
    result = sarif["runs"][0]["results"][0]
    assert sarif["version"] == "2.1.0" and result["level"] == "error"
    location = result["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "fixtures/clinic/broken/slots.html"
    assert location["region"]["startLine"] == 6
    summary = (tmp_path / "summary.md").read_text()
    assert summary.startswith(COMMENT_MARKER)
    assert "`fixtures/clinic/broken/slots.html:6`" in summary and "```diff" in summary


def test_an_accessible_journey_exits_0(tmp_path: Path) -> None:
    assert main(["run", str(JOURNEYS / "clinic-accessible.json"), "--out", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "report.json").read_text())["verdict"]["key"] == "passed"


def test_a_baseline_fails_only_on_new_findings(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    journey = str(JOURNEYS / "clinic-broken.json")
    main(["run", journey, "--out", str(tmp_path / "a"), "--write-baseline", str(baseline)])
    code = main(["run", journey, "--out", str(tmp_path / "b"), "--baseline", str(baseline)])
    report = json.loads((tmp_path / "b" / "report.json").read_text())
    assert code == 0
    assert report["baseline"] == {"used": True, "new": [], "fixed": []}
    assert "Nothing new compared with the baseline" in report["verdict"]["explanation"]


def test_manifest_journeys_run_by_key(tmp_path: Path) -> None:
    code = main(
        [
            "run",
            str(ROOT / "fixtures/benchmark/journey-manifest.json"),
            "--key",
            "bench-no-focus-style",
            "--site-dir",
            str(ROOT / "fixtures/clinic"),
            "--out",
            str(tmp_path),
            "--format",
            "json",
        ]
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert code == 1 and report["verdict"]["key"] == "failing"
    assert any(row["rule_id"] == "focus-visible" for row in report["findings"])


def test_setup_errors_exit_4(tmp_path: Path, capsys, monkeypatch) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"name": "x", "goal": "do it", "start_url": "ftp://x"}))
    assert main(["validate", str(bad)]) == 4
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    code = main(
        [
            "run",
            str(JOURNEYS / "wikipedia-search.json"),
            "--provider",
            "groq",
            "--model",
            "m",
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 4 and "GROQ_API_KEY" in capsys.readouterr().err
    assert main(["run", str(JOURNEYS / "wikipedia-search.json"), "--out", str(tmp_path)]) == 4
    missing = tmp_path / "missing.json"
    missing.write_text(
        json.dumps(
            {
                "name": "x",
                "goal": "do it",
                "site_dir": "nowhere",
                "plan": [{"action": "tab"}],
                "success": {"text_present": "x"},
            }
        )
    )
    assert main(["run", str(missing), "--out", str(tmp_path / "m")]) == 4
    broken_baseline = tmp_path / "baseline.json"
    broken_baseline.write_text("{not json")
    journey = str(JOURNEYS / "clinic-accessible.json")
    assert main(["run", journey, "--out", str(tmp_path), "--baseline", str(broken_baseline)]) == 4


def test_sarif_has_a_category_per_journey_and_paths_from_the_repository_root(
    tmp_path: Path,
) -> None:
    from accesspath.report import git_relative, to_sarif

    main(["run", str(JOURNEYS / "clinic-broken.json"), "--repo", str(ROOT), "--out", str(tmp_path)])
    summary = json.loads((tmp_path / "report.json").read_text())
    summary["code_root"] = "web"
    sarif = to_sarif(summary)["runs"][0]
    assert sarif["automationDetails"]["id"] == (
        "accesspath/clinic-appointment-booking-keyboard-barrier-control/"
    )
    uri = sarif["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert uri == "web/fixtures/clinic/broken/slots.html"
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "web").mkdir()
    assert git_relative(checkout / "web") == ("web", checkout.resolve())
    assert git_relative(checkout)[0] == ""


def test_init_and_validate(tmp_path: Path) -> None:
    path = tmp_path / "journey.json"
    assert main(["init", str(path)]) == 0
    assert main(["validate", str(path)]) == 0
    assert main(["init", str(path)]) == 4  # never overwrites without --force
    assert isinstance(load_journey(path), JourneyFileV1)
    for name in (
        "clinic-accessible",
        "clinic-broken",
        "no-focus-style",
        "wikipedia-search",
        "todomvc",
    ):
        assert main(["validate", str(JOURNEYS / f"{name}.json")]) == 0


@pytest.mark.parametrize(
    "data",
    [
        {
            "name": "x",
            "goal": "do it",
            "start_url": "https://a.example/",
            "site_dir": "s",
            "success": {"url_contains": "/done"},
        },
        {"name": "x", "goal": "do it", "start_url": "https://a.example/"},
        {
            "name": "x",
            "goal": "do it",
            "start_url": "https://u:p@a.example/",
            "success": {"url_contains": "/d"},
        },
        {
            "name": "x",
            "goal": "do it",
            "site_dir": "s",
            "start_path": "x",
            "success": {"url_contains": "/d"},
        },
    ],
)
def test_journey_files_are_validated(data: dict) -> None:
    with pytest.raises(ValueError):
        JourneyFileV1.model_validate(data)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_the_pr_comment_is_updated_not_duplicated() -> None:
    calls = []

    def opener(request, timeout):
        calls.append((request.get_method(), request.full_url))
        if request.get_method() == "GET":
            body = [
                {"id": 1, "body": "unrelated"},
                {"id": 5, "body": f"> quoting {COMMENT_MARKER}"},
                {"id": 7, "body": f"{COMMENT_MARKER}\nold"},
            ]
        else:
            body = {"html_url": "https://github.com/o/r/pull/3#issuecomment-7"}
        return _Response(json.dumps(body).encode())

    url = upsert_pr_comment(repository="o/r", pull_number=3, body="new", token="t", opener=opener)
    assert url.endswith("issuecomment-7")
    assert calls[-1] == ("PATCH", "https://api.github.com/repos/o/r/issues/comments/7")
    # Another action call on the same PR keeps its own comment.
    upsert_pr_comment(
        repository="o/r", pull_number=3, body="x", token="t", comment_id="gate", opener=opener
    )
    assert calls[-1][0] == "POST"

    def empty(request, timeout):
        calls.append((request.get_method(), request.full_url))
        body = [] if request.get_method() == "GET" else {"html_url": "https://x/new"}
        return _Response(json.dumps(body).encode())

    assert (
        upsert_pr_comment(repository="o/r", pull_number=3, body="b", token="t", opener=empty)
        == "https://x/new"
    )
    assert calls[-1][0] == "POST"
    with pytest.raises(GitHubError):
        upsert_pr_comment(repository="bad repo", pull_number=3, body="b", token="t", opener=empty)
    with pytest.raises(GitHubError):
        upsert_pr_comment(repository="o/r", pull_number=3, body="b", token="", opener=empty)
