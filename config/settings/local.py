"""Local development settings. Values come from the local .env file."""

import os
from pathlib import Path


def _load_local_env() -> None:
    """Load the developer .env file without overriding an existing environment."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

from .base import *  # noqa: E402, F403

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
