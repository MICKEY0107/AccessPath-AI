"""Short-lived handling for user-supplied planner API keys.

A key typed into the run form is never written to the database. The web
process seals it with Fernet (keyed from ``SECRET_KEY``) and hands only the
ciphertext to the worker through the task arguments, so the broker never sees
the raw key either. The worker opens it, uses it in memory, and scrubs it from
anything persisted for the run.
"""

from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

# Long enough for a queued run to wait behind another run on the single worker.
CREDENTIAL_TTL_SECONDS = 60 * 60
REDACTED = "[redacted]"
API_KEY_MAX_LENGTH = 512
MODEL_MAX_LENGTH = 255
_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]*$")


class CredentialError(ValueError):
    """The sealed key is missing, tampered with, or past its lifetime."""


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"accesspath.run-credential:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode()).decode()


def open_api_key(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode(), ttl=CREDENTIAL_TTL_SECONDS).decode()
    except InvalidToken as error:
        raise CredentialError("RUN_CREDENTIAL_INVALID_OR_EXPIRED") from error


def validate_api_key(api_key: str) -> str | None:
    """Return a user-facing problem with a typed key, or None when it looks usable."""
    if len(api_key) > API_KEY_MAX_LENGTH:
        return "The API key is too long."
    if any(character.isspace() for character in api_key):
        return "The API key must not contain spaces."
    return None


def validate_model(model: str) -> str | None:
    """Return a user-facing problem with a typed model id, or None when it looks usable."""
    if len(model) > MODEL_MAX_LENGTH:
        return "The model name is too long."
    if not _MODEL_PATTERN.match(model):
        return "Enter a model id such as openai/gpt-4.1-mini, without spaces."
    return None


def mask_api_key(api_key: str) -> str:
    """Show just enough of a key to recognise it in evidence, never enough to reuse it."""
    if len(api_key) <= 8:
        return "••••"
    return f"••••{api_key[-4:]}"


def scrub(value: object, secrets: list[str]) -> object:
    """Replace every occurrence of a secret inside nested JSON-like data."""
    secrets = [secret for secret in secrets if secret]
    if not secrets:
        return value
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, REDACTED)
        return value
    if isinstance(value, dict):
        return {key: scrub(item, secrets) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [scrub(item, secrets) for item in value]
    return value
