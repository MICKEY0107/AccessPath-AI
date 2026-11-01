"""Post or update one AccessPath comment on a pull request (GitHub REST, no extra tools)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .report import COMMENT_MARKER

API = "https://api.github.com"
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


class GitHubError(RuntimeError):
    pass


def _call(method: str, url: str, token: str, body: dict | None, opener: Callable) -> Any:
    request = Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AccessPathAI-cli",
            "Content-Type": "application/json",
        },
    )
    try:
        with opener(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except HTTPError as error:
        raise GitHubError(f"GitHub API {method} failed with HTTP {error.code}") from None
    except URLError as error:
        raise GitHubError(f"GitHub API unreachable: {error.reason}") from None


def comment_marker(comment_id: str = "") -> str:
    """The hidden first line that identifies one AccessPath comment (one per action call)."""
    clean = re.sub(r"[^A-Za-z0-9_.-]", "", comment_id)[:60]
    return f"<!-- accesspath-report:{clean} -->" if clean else COMMENT_MARKER


def upsert_pr_comment(
    *,
    repository: str,
    pull_number: int,
    body: str,
    token: str,
    comment_id: str = "",
    opener: Callable = urlopen,
) -> str:
    """Update the earlier AccessPath comment on the PR, or create one; returns its URL.

    Only a comment that *starts* with this call's marker is updated, so a person quoting
    the report, or another AccessPath call on the same PR, is never overwritten.
    """
    if not REPOSITORY.match(repository):
        raise GitHubError("Set the repository as owner/repo (GITHUB_REPOSITORY).")
    if pull_number < 1:
        raise GitHubError("Give the pull request number with --pr.")
    if not token:
        raise GitHubError("Set GITHUB_TOKEN so the comment can be posted.")
    marker = comment_marker(comment_id)
    lines = body.splitlines()
    if lines and lines[0].strip().startswith("<!-- accesspath-report"):
        lines = lines[1:]
    body = "\n".join([marker, *lines])
    body = body[:60000]
    base = f"{API}/repos/{repository}/issues/{pull_number}/comments"
    for page in range(1, 6):
        comments = _call("GET", f"{base}?per_page=100&page={page}", token, None, opener) or []
        for comment in comments:
            if (comment.get("body") or "").lstrip().startswith(marker):
                url = f"{API}/repos/{repository}/issues/comments/{comment['id']}"
                updated = _call("PATCH", url, token, {"body": body}, opener)
                return updated.get("html_url", url)
        if len(comments) < 100:
            break
    created = _call("POST", base, token, {"body": body}, opener)
    return created.get("html_url", base)
