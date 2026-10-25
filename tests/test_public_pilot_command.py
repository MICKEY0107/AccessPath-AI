from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_public_pilot_requires_explicit_live_target_confirmation() -> None:
    with pytest.raises(CommandError, match="RUN_APPROVED_LIVE_TESTS=true"):
        call_command("run_public_pilot", stdout=StringIO())


@pytest.mark.django_db
def test_public_pilot_rejects_an_empty_matrix(monkeypatch) -> None:
    monkeypatch.setenv("RUN_APPROVED_LIVE_TESTS", "true")

    with pytest.raises(CommandError, match="Count must be at least one"):
        call_command(
            "run_public_pilot",
            confirm_approved_target=True,
            count=0,
            stdout=StringIO(),
        )
