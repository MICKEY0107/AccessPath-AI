"""Shared test fixtures: the app requires sign-in, so the default client is signed in."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user("tester", password="correct horse battery")


@pytest.fixture
def client(user) -> Client:
    signed_in = Client()
    signed_in.force_login(user)
    return signed_in


@pytest.fixture
def anonymous_client() -> Client:
    return Client()
