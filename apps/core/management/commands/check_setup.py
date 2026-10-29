"""Print what is set up and how to fix what is not (the Status page, in a terminal)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.core.setup_checks import ERROR, run_checks, summary

MARKS = {"ok": "ok  ", "warn": "WARN", "error": "FAIL", "info": "info"}


class Command(BaseCommand):
    help = "Check the database, worker, browser, demo site, axe-core, git and AI providers."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--strict", action="store_true", help="Exit with an error on any FAIL.")

    def handle(self, *args, **options) -> None:
        checks = run_checks()
        group = ""
        for check in checks:
            if check.group != group:
                group = check.group
                self.stdout.write(f"\n{group}")
            self.stdout.write(f"  [{MARKS[check.status]}] {check.label}: {check.detail}")
            if check.fix and check.status != "ok":
                self.stdout.write(f"         fix: {check.fix}")
        overall = summary(checks)
        self.stdout.write("")
        if overall == ERROR:
            self.stdout.write(self.style.ERROR("Something needs fixing (see FAIL above)."))
            if options["strict"]:
                raise CommandError("check_setup found problems.")
        else:
            self.stdout.write(self.style.SUCCESS("Ready."))
