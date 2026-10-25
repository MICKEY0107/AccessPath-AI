from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="", GEMINI_MODEL="")
def test_fixture_matrix_refuses_to_create_non_gemini_evidence() -> None:
    with pytest.raises(CommandError, match="GEMINI_API_KEY is required"):
        call_command("run_fixture_matrix", stdout=StringIO())


@pytest.mark.django_db
@override_settings(GEMINI_API_KEY="configured", GEMINI_MODEL="models/verified")
def test_fixture_matrix_requires_at_least_one_case() -> None:
    with pytest.raises(CommandError, match="At least one matrix case is required"):
        call_command(
            "run_fixture_matrix",
            accessible_count=0,
            broken_count=0,
            stdout=StringIO(),
        )


@pytest.mark.django_db
@override_settings(OPENROUTER_API_KEY="", OPENROUTER_MODEL="")
def test_fixture_matrix_refuses_unconfigured_openrouter_evidence() -> None:
    with pytest.raises(CommandError, match="OPENROUTER_API_KEY is required"):
        call_command("run_fixture_matrix", provider="openrouter", stdout=StringIO())
