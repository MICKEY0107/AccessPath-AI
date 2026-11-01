"""Prepare a complete, offline demonstration in one command."""

from __future__ import annotations

import secrets
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.codebase.demo import ensure_demo_binding
from apps.journeys.models import ExecutionMode, Journey
from apps.runs.models import PlannerProvider, Run
from apps.runs.report import build_report
from apps.runs.services import execute_configured_run, fail_run
from engine.rules import RuleConfigV1

QUICK_RUNS = (
    "clinic-accessible-booking",
    "clinic-keyboard-trap-control",
    "bench-newsletter-div-button",
    "bench-no-focus-style",
    "bench-unnamed-icons",
    "bench-nav-no-skip",
)

# One team rule on the library page, so the demo shows custom rules in a report.
DEMO_CUSTOM_RULE = {
    "id": "custom-apply-button-reached-quickly",
    "title": "Apply button reached quickly",
    "check": "selector_reachable_within",
    "selector": ".content button",
    "max_tabs": 4,
    "criterion": "2.4.1",
    "severity": "serious",
    "fix_hint": "Add a skip link to the main content, or put the form before the long menu.",
}


class Command(BaseCommand):
    help = (
        "Set up the offline demo: a demo account, the clinic and benchmark journeys, the "
        "bundled demo repository linked to them, one team rule, and scripted runs so the "
        "reports are ready to open. Safe to run again. Needs no API key and no GitHub."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--username", default="demo")
        parser.add_argument(
            "--password",
            default="",
            help="Password for the demo account. Without it a new account gets a random "
            "password (printed once) and an existing account keeps its password.",
        )
        parser.add_argument(
            "--runs",
            choices=["quick", "all", "none"],
            default="quick",
            help="quick: 6 scripted runs (about a minute); all: every fixture journey.",
        )

    def handle(self, *args, **options) -> None:
        user, password = self._user(options["username"], options["password"])
        call_command("seed_fixture_journeys", stdout=StringIO())
        journeys = {
            journey.evaluation_config.get("journey_key"): journey
            # Only the bundled demo-site journeys: public journeys reach live websites.
            for journey in Journey.objects.filter(
                is_active=True, execution_mode=ExecutionMode.FIXTURE
            )
            if journey.evaluation_config.get("journey_key")
        }
        if not journeys:
            raise CommandError(
                "No fixture journeys were seeded; check fixtures/*/journey-manifest.json."
            )
        self.stdout.write(f"Journeys: {len(journeys)} demo journeys are ready.")

        library = journeys.get("bench-nav-no-skip")
        if library is not None:
            config = RuleConfigV1.model_validate(library.rule_config or {})
            if not any(item.id == DEMO_CUSTOM_RULE["id"] for item in config.custom):
                data = config.model_dump(mode="json")
                data["custom"].append(DEMO_CUSTOM_RULE)
                library.rule_config = RuleConfigV1.model_validate(data).model_dump(mode="json")
                library.save(update_fields=["rule_config", "updated_at"])
            self.stdout.write(
                "Rules: added the team rule “Apply button reached quickly” to the library page."
            )

        binding, linked = ensure_demo_binding(user)
        if binding.status != "ready":
            raise CommandError(f"The demo repository could not be prepared: {binding.error}")
        self.stdout.write(
            f"Code: demo repository ready ({binding.summary.get('repo_files', 0)} files) "
            f"and linked to {linked} journeys."
        )

        journeys = {key: Journey.objects.get(pk=journey.pk) for key, journey in journeys.items()}
        keys = {"quick": QUICK_RUNS, "all": tuple(sorted(journeys)), "none": ()}[options["runs"]]
        results = []
        for key in keys:
            journey = journeys.get(key)
            if journey is None:
                continue
            run = Run.objects.create(
                journey=journey,
                planner_provider=PlannerProvider.FIXTURE,
                planner_metadata={"started_by": user.pk},
            )
            try:
                execute_configured_run(run)
            except Exception as error:  # One failed run must not stop the demo.
                fail_run(
                    run,
                    outcome="system_error",
                    reason="DEMO_RUN_FAILED",
                    detail=f"{type(error).__name__}: {error}",
                )
            run.refresh_from_db()
            report = build_report(run, user)
            results.append((journey.name, report["verdict"]["label"], report["stats"], run.id))
            self.stdout.write(f"Run: {journey.name} → {report['verdict']['label']}")

        base = settings.DEMO_SITE_URL.rstrip("/")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("The demo is ready."))
        self.stdout.write(f"Open {base}/runs/ and sign in as “{user.get_username()}”.")
        if password:
            self.stdout.write(f"Password: {password}   (shown once; change it with changepassword)")
        else:
            self.stdout.write("Password: unchanged (use --password to set one).")
        if results:
            self.stdout.write("\nReports:")
            for name, label, stats, run_id in results:
                self.stdout.write(
                    f"  {label:<26} {stats['confirmed']} confirmed, {stats['review']} to review — "
                    f"{name}\n      {base}/runs/{run_id}/"
                )
        self.stdout.write(f"\nSystem check: {base}/status/")

    def _user(self, username: str, password: str):
        model = get_user_model()
        user = model.objects.filter(**{model.USERNAME_FIELD: username}).first()
        if user is None:
            password = password or secrets.token_urlsafe(9)
            user = model.objects.create_user(username, password=password)
            self.stdout.write(f"Account: created “{username}”.")
            return user, password
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(f"Account: “{username}” exists; password updated.")
        else:
            self.stdout.write(f"Account: “{username}” exists.")
        return user, password
