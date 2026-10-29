"""Check a suggested fix on a temporary copy of a fixture site.

Only the project's own fixture pages (``fixtures/clinic/`` in AccessPath's own
folder, passed as ``snapshot_root``) are ever served this way: they are static HTML
that AccessPath ships with. Files from a cloned repository are never served or run,
even when the repository has a folder of the same name; for those, the patch is
shown for people to apply.
"""

from __future__ import annotations

import functools
import shutil
import tempfile
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .artifacts import LocalArtifactStore
from .executor import KeyboardExecutor
from .planner import FixturePlanPlanner
from .rules import ActiveRuleSet

FIXTURE_PREFIX = "fixtures/clinic/"


@dataclass
class Verification:
    resolved: bool
    outcome: str
    detail: str


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def can_verify(fix: dict[str, Any] | None) -> bool:
    return bool(fix and fix.get("edits") and str(fix.get("path", "")).startswith(FIXTURE_PREFIX))


def verify_fixture_fix(
    *,
    snapshot_root: Path,
    fix: dict[str, Any],
    finding: dict[str, Any],
    start_url: str,
    completion_policy: dict[str, Any],
    barrier_check: dict[str, Any] | None,
    plan: dict[str, Any],
    rule_set: ActiveRuleSet,
    browser_executable_path: str | None = None,
) -> Verification:
    """Apply ``fix`` to a copy of the fixture site and re-run the journey's scripted plan."""
    if not can_verify(fix):
        raise ValueError("Only fixes to the project's own fixture pages can be verified.")
    source = (snapshot_root / "fixtures" / "clinic").resolve()
    with tempfile.TemporaryDirectory(prefix="accesspath-verify-") as temporary:
        site = Path(temporary) / "site"
        shutil.copytree(source, site, symlinks=False)
        target = (site / fix["path"][len(FIXTURE_PREFIX):]).resolve()
        target.relative_to(site.resolve())  # Refuse anything outside the copy.
        lines = target.read_text(encoding="utf-8").splitlines()
        for number, replacement in fix["edits"].items():
            index = int(number) - 1
            if not 0 <= index < len(lines):
                raise ValueError("The fix names a line that is not in the file.")
            lines[index] = replacement
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")

        handler = functools.partial(_Quiet, directory=str(site))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{server.server_port}"
            path = urlparse(start_url).path
            run_id = uuid4()
            result = KeyboardExecutor(
                run_id=run_id,
                start_url=f"{origin}{path}",
                allowed_origins=[origin],
                completion_policy=completion_policy,
                barrier_check=barrier_check,
                max_steps=40,
                action_timeout_ms=5000,
                headless=True,
                browser_executable_path=browser_executable_path,
                artifact_store=LocalArtifactStore(Path(temporary) / "artifacts", run_id),
                on_step=lambda step, artifacts: None,
                rule_set=rule_set,
            ).run(FixturePlanPlanner(plan).actions())
        finally:
            server.shutdown()
            thread.join(timeout=2)
    still = [
        item
        for item in result.findings
        if item.rule_id == finding.get("rule_id") and item.status == "confirmed"
    ]
    if still:
        return Verification(
            False, result.outcome, f"The re-run still confirms this barrier: {still[0].summary}"
        )
    if result.outcome == "completed":
        ending = " and the journey now completes."
    else:
        ending = (
            f". The replayed plan was written for the unfixed page, so the run itself ended "
            f"as “{result.outcome}”; a live AI run would follow the fixed page."
        )
    return Verification(
        True,
        result.outcome,
        "With the patch applied to a temporary copy, the re-run no longer confirms this "
        f"barrier{ending}",
    )
