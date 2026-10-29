"""Clone and index a bound repository. Runs in the worker, never in a web request."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime

from django.conf import settings

from apps.runs.credentials import scrub
from engine.code_index import build_index, save_index
from engine.repo_clone import RepoCloneError, clone_snapshot, validate_branch, validate_repo_url

from .models import RepoBinding, RepoStatus


def analyze_binding(binding: RepoBinding, *, token: str = "") -> RepoBinding:
    """Fetch the latest commit as plain files and rebuild the code index."""
    binding.status = RepoStatus.CLONING
    binding.error = ""
    binding.save(update_fields=["status", "error", "updated_at"])
    try:
        url = validate_repo_url(
            binding.repo_url,
            settings.REPO_ALLOWED_HOSTS,
            allow_file_urls=settings.REPO_ALLOW_FILE_URLS,
        )
        snapshot = clone_snapshot(
            url,
            binding.source_dir,
            branch=validate_branch(binding.branch),
            token=token,
            timeout_seconds=settings.REPO_CLONE_TIMEOUT_SECONDS,
            max_bytes=settings.REPO_MAX_BYTES,
            max_files=settings.REPO_MAX_FILES,
            allow_file_urls=settings.REPO_ALLOW_FILE_URLS,
        )
        index = build_index(snapshot.path)
        save_index(index, binding.index_path)
    except RepoCloneError as error:
        binding.status = RepoStatus.FAILED
        binding.error = scrub(str(error), [token])
    except Exception as error:  # Never leave a binding stuck in "cloning".
        binding.status = RepoStatus.FAILED
        binding.error = scrub(f"{type(error).__name__}: {error}", [token])[:600]
    else:
        binding.status = RepoStatus.READY
        binding.commit_sha = snapshot.commit_sha
        binding.summary = {
            **index.summary(),
            "repo_files": snapshot.file_count,
            "repo_bytes": snapshot.total_bytes,
        }
        binding.analysed_at = datetime.now(UTC)
    binding.save()
    return binding


def remove_binding_files(binding: RepoBinding) -> None:
    shutil.rmtree(binding.storage_dir, ignore_errors=True)
