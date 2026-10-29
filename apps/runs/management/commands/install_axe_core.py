"""Download the pinned axe-core release used for page-level checks."""

from __future__ import annotations

import hashlib
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

SOURCE = "https://cdn.jsdelivr.net/npm/axe-core@{version}/axe.min.js"


class Command(BaseCommand):
    help = "Download axe-core (MPL-2.0) to AXE_CORE_PATH so runs can include its page rules."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--version", default=settings.AXE_CORE_VERSION)
        parser.add_argument(
            "--sha256", default="", help="Refuse the download unless it has this SHA-256 hash."
        )

    def handle(self, *args, **options) -> None:
        version = options["version"]
        url = SOURCE.format(version=version)
        request = Request(url, headers={"User-Agent": "AccessPathAI/1.0"})
        try:
            with urlopen(request, timeout=60) as response:
                body = response.read()
        except OSError as error:
            raise CommandError(f"Could not download {url}: {error}") from error
        header = body[:200].decode("utf-8", "replace")
        if f"axe v{version}" not in header:
            raise CommandError("The download does not look like the requested axe-core release.")
        digest = hashlib.sha256(body).hexdigest()
        if options["sha256"] and options["sha256"].lower() != digest:
            raise CommandError(f"SHA-256 mismatch: got {digest}")
        path = settings.AXE_CORE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        self.stdout.write(
            self.style.SUCCESS(f"Saved axe-core {version} to {path} (sha256 {digest}).")
        )
