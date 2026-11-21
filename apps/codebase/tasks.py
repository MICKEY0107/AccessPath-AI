"""Worker task: clone and index a repository away from the web process."""

from __future__ import annotations

from celery import shared_task

from apps.runs.credentials import CredentialError, open_api_key

from .models import RepoBinding, RepoStatus
from .services import analyze_binding


@shared_task(name="accesspath.analyze_repository", queue="repository")
def analyze_repository(binding_id: int, credential_token: str = "") -> str:
    """``credential_token`` is a sealed, short-lived access token; it is never stored."""
    binding = RepoBinding.objects.filter(pk=binding_id).first()
    if binding is None:
        return "missing"
    token = ""
    if credential_token:
        try:
            token = open_api_key(credential_token)
        except CredentialError:
            binding.status = RepoStatus.FAILED
            binding.error = "The access token expired before cloning started. Enter it again."
            binding.save(update_fields=["status", "error", "updated_at"])
            return binding.status
    return analyze_binding(binding, token=token).status
