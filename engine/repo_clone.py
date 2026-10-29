"""Fetch a repository as a read-only snapshot of plain files.

Safety rules, in order:

* Only https URLs on an allow-listed host (GitHub, GitLab, Bitbucket) of the form
  /owner/repo; no credentials, query or fragment in the URL.
* The access token is passed in an HTTP header through environment variables, never
  in the URL or on the command line, and is scrubbed from every error message.
* git runs with hooks disabled, symlinks checked out as plain text files, no
  submodules, no LFS downloads, no tags, depth 1, a time limit, and no access to
  the server's own git configuration or credential helpers.
* After cloning, the .git folder is deleted, so what remains is plain files. Size
  and file-count limits are enforced, and nothing in the copy is ever run.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

BRANCH_PATTERN = re.compile(r"^(?!-)(?!.*\.\.)(?!.*//)[A-Za-z0-9._/-]{1,100}(?<!/)(?<!\.lock)$")
REPO_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}(\.git)?/?$")
TOKEN_USERS = {"github.com": "x-access-token", "gitlab.com": "oauth2", "bitbucket.org": "x-token-auth"}


class RepoCloneError(ValueError):
    """A plain-language reason the repository could not be fetched."""


@dataclass(frozen=True)
class RepoSnapshot:
    path: Path
    commit_sha: str
    file_count: int
    total_bytes: int


def validate_repo_url(
    url: str, allowed_hosts: tuple[str, ...], *, allow_file_urls: bool = False
) -> str:
    """Return a normalised clone URL, or raise RepoCloneError with the reason."""
    url = url.strip()
    parsed = urlparse(url)
    if allow_file_urls and parsed.scheme == "file":
        return url
    if parsed.scheme != "https":
        raise RepoCloneError("Use an https:// repository address.")
    if parsed.username or parsed.password:
        raise RepoCloneError("Do not put a username or token in the address; use the token field.")
    if parsed.query or parsed.fragment or parsed.params:
        raise RepoCloneError("Remove the ?query or #fragment from the address.")
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts or parsed.port not in (None, 443):
        raise RepoCloneError(f"Only {', '.join(allowed_hosts)} repositories can be added.")
    if not REPO_PATH_PATTERN.match(parsed.path):
        raise RepoCloneError("Use the repository address, like https://github.com/owner/repo.")
    path = parsed.path.rstrip("/")
    if not path.endswith(".git"):
        path += ".git"
    return f"https://{host}{path}"


def validate_branch(branch: str) -> str:
    branch = branch.strip()
    if branch and not BRANCH_PATTERN.match(branch):
        raise RepoCloneError("That branch name is not valid.")
    return branch


def _scrub(text: str, token: str) -> str:
    if token:
        text = text.replace(token, "[redacted]")
        encoded = base64.b64encode(token.encode()).decode()
        text = text.replace(encoded, "[redacted]")
    return text[-600:]


def _git_env(url: str, token: str, home: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": home,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "LC_ALL": "C",
    }
    for name in ("HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy", "SSL_CERT_FILE",
                 "GIT_SSL_CAINFO", "REQUESTS_CA_BUNDLE"):
        if name in os.environ:
            env[name] = os.environ[name]
    if token:
        host = (urlparse(url).hostname or "").lower()
        user = TOKEN_USERS.get(host, "x-access-token")
        basic = base64.b64encode(f"{user}:{token}".encode()).decode()
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "http.extraHeader",
                "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
            }
        )
    return env


def clone_snapshot(
    url: str,
    destination: Path,
    *,
    branch: str = "",
    token: str = "",
    timeout_seconds: int = 120,
    max_bytes: int = 200 * 1024 * 1024,
    max_files: int = 20_000,
    allow_file_urls: bool = False,
) -> RepoSnapshot:
    """Shallow-clone into ``destination`` (replaced if present) and strip .git."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="accesspath-git-home-") as home:
        command = [
            "git",
            "-c", "core.hooksPath=" + os.devnull,
            "-c", "core.symlinks=false",
            "-c", "core.fsmonitor=false",
            "-c", "credential.helper=",
            "-c", "submodule.recurse=false",
            "-c", "protocol.allow=never",
            "-c", "protocol.https.allow=always",
        ]
        if allow_file_urls:
            command += ["-c", "protocol.file.allow=always"]
        command += ["clone", "--depth", "1", "--single-branch", "--no-tags",
                    "--no-recurse-submodules"]
        if branch:
            command += ["--branch", branch]
        command += ["--", url, str(destination)]
        env = _git_env(url, token, home)
        try:
            completed = subprocess.run(
                command, env=env, capture_output=True, text=True, timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            shutil.rmtree(destination, ignore_errors=True)
            raise RepoCloneError(f"Cloning took longer than {timeout_seconds} seconds.") from error
        if completed.returncode != 0:
            shutil.rmtree(destination, ignore_errors=True)
            stderr = _scrub(completed.stderr or "", token)
            if "Authentication failed" in stderr or "could not read Username" in stderr or (
                "403" in stderr or "401" in stderr
            ):
                raise RepoCloneError(
                    "The repository needs a valid access token (or the token cannot read it)."
                )
            if "not found" in stderr.lower() and "branch" in stderr.lower():
                raise RepoCloneError("That branch was not found in the repository.")
            raise RepoCloneError(f"git could not clone the repository: {stderr.strip()[-300:]}")
        sha = subprocess.run(
            ["git", "-C", str(destination), "rev-parse", "HEAD"],
            env=env, capture_output=True, text=True, timeout=30, check=False,
        ).stdout.strip()
    shutil.rmtree(destination / ".git", ignore_errors=True)
    total_bytes = 0
    file_count = 0
    for path in destination.rglob("*"):
        if path.is_symlink():
            path.unlink()
            continue
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
        if file_count > max_files or total_bytes > max_bytes:
            shutil.rmtree(destination, ignore_errors=True)
            raise RepoCloneError(
                f"The repository is too large to analyse (limit {max_files} files, "
                f"{max_bytes // (1024 * 1024)} MB)."
            )
    return RepoSnapshot(
        path=destination, commit_sha=sha[:40], file_count=file_count, total_bytes=total_bytes
    )
