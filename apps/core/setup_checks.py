"""What is set up and what is not, with the exact fix for each item.

Used by the Status page and by ``python manage.py check_setup``. Every check is
quick (at most about a second) and never shows a key, only whether one is set.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, WARN, ERROR, INFO = "ok", "warn", "error", "info"


@dataclass
class Check:
    group: str
    label: str
    status: str
    detail: str
    fix: str = ""
    pill: str = ""  # Overrides the status label, e.g. "Note" for plain information.

    def as_dict(self) -> dict[str, str]:
        return {
            "group": self.group,
            "label": self.label,
            "status": self.status,
            "detail": self.detail,
            "fix": self.fix,
        }


def _database() -> Check:
    try:
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception as error:
        return Check(
            "Core",
            "Database",
            ERROR,
            f"Cannot reach the database ({type(error).__name__}).",
            "Start it with docker compose up -d db, and check POSTGRES_* in .env.",
        )
    if pending:
        return Check(
            "Core",
            "Database",
            ERROR,
            f"{len(pending)} migration(s) not applied.",
            "python manage.py migrate",
        )
    return Check("Core", "Database", OK, "Connected; all migrations applied.")


def _worker(timeout: float) -> Check:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return Check("Core", "Worker", OK, "Tasks run in this process (eager mode).")
    try:
        from config.celery import app

        # Fail fast when the broker is down instead of letting kombu retry for seconds.
        with app.connection_for_write() as connection:
            connection.ensure_connection(max_retries=1, interval_start=0, timeout=timeout)
            replies = app.control.ping(timeout=timeout, connection=connection) or []
    except Exception as error:
        return Check(
            "Core",
            "Worker",
            ERROR,
            f"Cannot reach the task queue ({type(error).__name__}).",
            "Start Redis and the worker: docker compose up -d redis worker",
        )
    if not replies:
        return Check(
            "Core",
            "Worker",
            ERROR,
            "No worker answered, so runs will wait in the queue.",
            "docker compose up -d worker  (or: celery -A config worker --concurrency=1)",
        )
    return Check("Core", "Worker", OK, f"{len(replies)} worker(s) answering.")


def _browser() -> Check:
    executable = settings.EVALUATOR_BROWSER_EXECUTABLE
    if executable:
        exists = Path(executable).exists()
        return Check(
            "Core",
            "Browser",
            OK if exists else ERROR,
            f"Using {executable}." if exists else f"{executable} does not exist.",
            "" if exists else "Fix EVALUATOR_BROWSER_EXECUTABLE in .env or leave it blank.",
        )
    roots = [
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
        str(Path.home() / ".cache" / "ms-playwright"),
        str(Path.home() / "AppData" / "Local" / "ms-playwright"),
    ]
    for root in filter(None, roots):
        if any(Path(root).glob("chromium*")):
            return Check("Core", "Browser", OK, "Playwright Chromium is installed.")
    return Check(
        "Core",
        "Browser",
        WARN,
        "Playwright's Chromium was not found where it usually is.",
        "python -m playwright install chromium  (the Docker image already has it)",
    )


def _fixture_site() -> Check:
    from engine.fixture_site import LOOPBACK_HOSTS, is_reachable

    origin = settings.FIXTURE_ALLOWED_ORIGINS[0] if settings.FIXTURE_ALLOWED_ORIGINS else ""
    if not origin:
        return Check(
            "Demo",
            "Demo site",
            WARN,
            "FIXTURE_ALLOWED_ORIGINS is empty.",
            "Set FIXTURE_ALLOWED_ORIGINS=http://127.0.0.1:8001 in .env.",
        )
    if is_reachable(origin):
        return Check("Demo", "Demo site", OK, f"Answering at {origin}.")
    if (urlparse(origin).hostname or "") in LOOPBACK_HOSTS:
        return Check(
            "Demo",
            "Demo site",
            OK,
            f"Nothing answers at {origin} here, so each demo run serves the bundled site itself.",
        )
    return Check(
        "Demo",
        "Demo site",
        ERROR,
        f"Nothing answers at {origin}, so demo journeys cannot run.",
        "docker compose up -d fixture  (or set FIXTURE_ALLOWED_ORIGINS=http://127.0.0.1:8001 "
        "and let runs serve the site themselves)",
    )


def _journeys() -> Check:
    from apps.journeys.models import Journey

    count = Journey.objects.filter(is_active=True).count()
    if not count:
        return Check(
            "Demo",
            "Journeys",
            WARN,
            "No journeys yet.",
            "python manage.py demo_setup  (or seed_fixture_journeys)",
        )
    return Check("Demo", "Journeys", OK, f"{count} active journeys.")


def _axe() -> Check:
    path = Path(settings.AXE_CORE_PATH)
    if path.is_file():
        return Check("Checks", "axe-core", OK, f"Installed ({path.stat().st_size // 1024} KB).")
    return Check(
        "Checks",
        "axe-core",
        INFO,
        "Not installed: the keyboard checks run, axe-core's page rules are reported as not "
        "checked.",
        "python manage.py install_axe_core",
    )


def _git_and_storage() -> list[Check]:
    checks = []
    git = shutil.which("git")
    checks.append(
        Check("Code", "git", OK, "Available for cloning repositories.")
        if git
        else Check(
            "Code",
            "git",
            WARN,
            "Not installed, so GitHub/GitLab repositories cannot be cloned "
            "(the demo repository still works).",
            "Rebuild the image: docker compose up -d --build",
        )
    )
    root = Path(settings.REPO_STORAGE_ROOT)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(Check("Code", "Repository storage", OK, f"Writable ({root})."))
    except OSError as error:
        checks.append(
            Check(
                "Code",
                "Repository storage",
                ERROR,
                f"Not writable: {error.strerror}.",
                "Check the repo_storage volume or REPO_STORAGE_ROOT.",
            )
        )
    return checks


def _providers(user, timeout: float) -> list[Check]:
    from apps.runs.model_settings import saved_for
    from engine.code_safety import code_safety

    saved = saved_for(user) if user is not None else {}
    checks = []
    for provider, label, key, model in (
        ("groq", "Groq", settings.GROQ_API_KEY, settings.GROQ_MODEL),
        ("gemini", "Gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL),
        ("openrouter", "OpenRouter", settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL),
    ):
        safety = code_safety(provider, model or "", settings.CODE_SAFE_PROVIDERS)
        private = "may read private code" if safety.safe else "not used for private code"
        if key or provider in saved:
            where = "server key in .env" if key else "your saved key"
            checks.append(
                Check(
                    "AI providers",
                    label,
                    OK,
                    f"Ready with the {where}; model {model or 'chosen per run'}; {private}.",
                )
            )
        else:
            checks.append(
                Check(
                    "AI providers",
                    label,
                    INFO,
                    "No key: type one in the run form or save one on Models.",
                    f"Set {provider.upper()}_API_KEY in .env, or use Models → Save & use.",
                )
            )
    if not settings.OLLAMA_BASE_URL:
        checks.append(
            Check(
                "AI providers",
                "Local Ollama",
                INFO,
                "Not configured (optional, free, private).",
                "Set OLLAMA_BASE_URL (Docker: http://host.docker.internal:11434) and OLLAMA_MODEL.",
            )
        )
    else:
        try:
            with urlopen(
                settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=timeout
            ) as response:
                models = [
                    item.get("name") for item in json.loads(response.read()).get("models", [])
                ]
            wanted = settings.OLLAMA_MODEL
            if wanted and wanted not in models:
                checks.append(
                    Check(
                        "AI providers",
                        "Local Ollama",
                        WARN,
                        f"Running, but {wanted} is not pulled.",
                        f"ollama pull {wanted}",
                    )
                )
            else:
                checks.append(
                    Check(
                        "AI providers", "Local Ollama", OK, f"Running with {len(models)} model(s)."
                    )
                )
        except Exception as error:
            checks.append(
                Check(
                    "AI providers",
                    "Local Ollama",
                    WARN,
                    f"Configured but not answering ({type(error).__name__}).",
                    "Start Ollama on the host (ollama serve) and check OLLAMA_BASE_URL.",
                )
            )
    checks.append(
        Check(
            "AI providers",
            "Scripted plans",
            OK,
            "Always available: the fixture provider replays reviewed plans with no AI.",
        )
    )
    return checks


def _security() -> list[Check]:
    checks = []
    secret = settings.SECRET_KEY or ""
    if "replace" in secret or len(secret) < 32:
        checks.append(
            Check(
                "Security",
                "Secret key",
                WARN,
                "DJANGO_SECRET_KEY looks like the example or is short; saved keys depend on it.",
                "Set a long random DJANGO_SECRET_KEY in .env "
                '(python -c "import secrets;print(secrets.token_urlsafe(50))").',
            )
        )
    else:
        checks.append(Check("Security", "Secret key", OK, "Set."))
    if settings.DEBUG:
        checks.append(
            Check(
                "Security",
                "Debug mode",
                INFO,
                "On: fine on your own computer, never on a shared server.",
                "DJANGO_DEBUG=false when others can reach the app.",
                pill="Note",
            )
        )
    return checks


def run_checks(user=None, *, timeout: float = 1.0) -> list[Check]:
    checks = [_database()]
    database_ok = checks[0].status == OK
    checks += [_worker(timeout), _browser()]
    checks += [_fixture_site()] + ([_journeys()] if database_ok else [])
    checks += [_axe(), *_git_and_storage()]
    if database_ok:
        checks += _providers(user, timeout)
    checks += _security()
    return checks


def summary(checks: list[Check]) -> str:
    if any(check.status == ERROR for check in checks):
        return ERROR
    if any(check.status == WARN for check in checks):
        return WARN
    return OK
