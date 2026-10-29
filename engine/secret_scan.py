"""Remove secrets from code before it is shown, stored in an index, or sent to an AI."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

REDACTED = "[redacted-secret]"

# Files that are never read at all.
BLOCKED_NAME_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"^\.env(\..*)?$",
        r"^\.npmrc$",
        r"^\.pypirc$",
        r"^\.netrc$",
        r"^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$",
        r".*\.(pem|key|p12|pfx|jks|keystore|kdbx|crt|cer|der)$",
        r".*(secret|credential|password).*\.(json|ya?ml|txt|ini|cfg|conf|toml|properties)$",
        r"^service[-_]?account.*\.json$",
    )
]
BLOCKED_DIRECTORIES = {
    ".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "coverage", "vendor",
    "venv", ".venv", "__pycache__", "target", ".cache", ".turbo", "secrets", ".idea", ".vscode",
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-(?:or-|proj-|ant-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
]
ASSIGNMENT = re.compile(
    r"""(?ix)
    ((?:api[_-]?key|secret|token|password|passwd|client[_-]?secret|access[_-]?key)
     [\w-]*\s*[:=]\s*)
    (["'])([^"'\s]{8,})\2
    """
)


def is_blocked_path(relative_path: str) -> bool:
    """True when a file must never be read (keys, env files, build output)."""
    path = PurePosixPath(relative_path)
    if any(part in BLOCKED_DIRECTORIES for part in path.parts[:-1]):
        return True
    return any(pattern.match(path.name) for pattern in BLOCKED_NAME_PATTERNS)


def redact(text: str) -> tuple[str, int]:
    """Replace secret-looking values; returns the cleaned text and how many were found."""
    count = 0
    for pattern in SECRET_PATTERNS:
        text, found = pattern.subn(REDACTED, text)
        count += found

    def _assignment(match: re.Match) -> str:
        nonlocal count
        count += 1
        return f"{match.group(1)}{match.group(2)}{REDACTED}{match.group(2)}"

    text = ASSIGNMENT.sub(_assignment, text)
    return text, count
