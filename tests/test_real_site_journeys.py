from unittest.mock import Mock, patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.journeys.models import Journey
from apps.journeys.real_sites import host_is_public
from apps.runs.models import PlannerProvider, Run
from engine.contracts import TargetPolicyV1
from engine.target_policy import TargetPolicy, is_local_or_private_host

PUBLIC_ADDRESS = [(2, 1, 6, "", ("93.184.215.14", 0))]
PRIVATE_ADDRESS = [(2, 1, 6, "", ("10.0.0.5", 0))]


def form_data(**overrides):
    data = {
        "name": "Example search",
        "start_url": "https://www.example.org/",
        "goal": "Search the site for accessibility using only the keyboard.",
        "success_url_contains": "search=accessibility",
        "success_text": "",
        "text_to_type": "accessibility",
        "extra_origins": "",
        "max_actions": "30",
    }
    data.update(overrides)
    return data


@pytest.fixture
def public_dns():
    with patch("apps.journeys.real_sites.socket.getaddrinfo", return_value=PUBLIC_ADDRESS):
        yield


def test_dashboard_creates_a_read_only_real_site_journey(client, db, public_dns) -> None:
    response = client.post(reverse("runs:create_journey"), form_data())

    journey = Journey.objects.get(name="Example search")
    assert response.status_code == 302
    assert journey.is_real_site
    assert journey.execution_mode == "public_read_only"
    assert journey.allowed_origins == ["https://www.example.org"]
    assert not journey.has_fixture_plan
    policy = TargetPolicyV1.model_validate(journey.evaluation_config["target_policy"])
    assert policy.allowed_methods == ["GET", "HEAD", "OPTIONS"]
    assert policy.allow_any_resource_origin is True
    assert policy.max_actions == 30
    planner = journey.evaluation_config["planner"]
    assert planner["allow_no_fallback"] is True
    assert planner["synthetic_values"] == {"text_to_type": "accessibility"}
    assert journey.completion_policy["signals"][0]["type"] == "url_contains"


def test_a_success_check_is_required(client, db, public_dns) -> None:
    response = client.post(
        reverse("runs:create_journey"), form_data(success_url_contains="", success_text="")
    )

    assert response.status_code == 400
    assert Journey.objects.count() == 0
    assert "at least one success check" in response.content.decode()


@override_settings(ALLOW_PRIVATE_NETWORKS=False)
def test_private_and_local_sites_are_refused(client, db) -> None:
    with patch("apps.journeys.real_sites.socket.getaddrinfo", return_value=PRIVATE_ADDRESS):
        intranet = client.post(
            reverse("runs:create_journey"), form_data(start_url="https://intranet.example/")
        )
    local = client.post(
        reverse("runs:create_journey"), form_data(start_url="http://127.0.0.1:8000/")
    )

    assert intranet.status_code == 400
    assert local.status_code == 400
    assert Journey.objects.count() == 0
    assert "private" in intranet.content.decode()


def test_host_check_rejects_unresolvable_names() -> None:
    import socket

    with patch("apps.journeys.real_sites.socket.getaddrinfo", side_effect=socket.gaierror):
        assert host_is_public("no-such-host.invalid") is False
    assert is_local_or_private_host("localhost")
    assert is_local_or_private_host("192.168.1.10")
    assert not is_local_or_private_host("cdn.example.net")


def test_real_site_policy_allows_public_cdn_resources_but_not_navigation_or_writes() -> None:
    policy = TargetPolicy(
        TargetPolicyV1(
            navigation_origins=["https://www.example.org"],
            resource_origins=["https://www.example.org"],
            navigation_path_prefixes=["/"],
            allow_any_resource_origin=True,
        )
    )

    cdn = policy.decide_request("https://cdn.example.net/app.js", method="GET", is_navigation=False)
    lan = policy.decide_request("http://192.168.0.2/x.png", method="GET", is_navigation=False)
    away = policy.decide_request("https://other.example/", method="GET", is_navigation=True)
    post = policy.decide_request("https://cdn.example.net/t", method="POST", is_navigation=False)

    assert cdn.allowed
    assert not lan.allowed and lan.code == "RESOURCE_PRIVATE_HOST_BLOCKED"
    assert not away.allowed and away.fatal
    assert not post.allowed


def test_fixture_planner_is_refused_for_a_real_site_journey(client, db, public_dns) -> None:
    client.post(reverse("runs:create_journey"), form_data())
    journey = Journey.objects.get(name="Example search")

    response = client.post(
        reverse("runs:start", kwargs={"journey_id": journey.id}),
        {"planner_provider": "fixture"},
        follow=True,
    )

    assert Run.objects.count() == 0
    assert "no scripted plan" in response.content.decode()


@override_settings(GROQ_API_KEY="server-key", GROQ_MODEL="openai/gpt-oss-20b")
def test_a_live_run_can_be_started_on_a_real_site_journey(client, db, public_dns) -> None:
    client.post(reverse("runs:create_journey"), form_data())
    journey = Journey.objects.get(name="Example search")

    with patch("apps.runs.views.execute_run.delay", return_value=Mock(id="t1")):
        response = client.post(
            reverse("runs:start", kwargs={"journey_id": journey.id}),
            {"planner_provider": "groq"},
        )

    run = Run.objects.get(journey=journey)
    assert response.status_code == 302
    assert run.planner_provider == PlannerProvider.GROQ


def test_real_site_journeys_can_be_removed_but_seeded_ones_cannot(client, db, public_dns) -> None:
    client.post(reverse("runs:create_journey"), form_data())
    journey = Journey.objects.get(name="Example search")
    seeded = Journey.objects.create(
        name="Seeded",
        goal="A seeded reference journey.",
        start_url="http://fixture/accessible/index.html",
        allowed_origins=["http://fixture"],
        evaluation_config={},
    )

    client.post(reverse("runs:remove_journey", kwargs={"journey_id": journey.id}))
    client.post(reverse("runs:remove_journey", kwargs={"journey_id": seeded.id}))

    journey.refresh_from_db()
    seeded.refresh_from_db()
    assert journey.is_active is False
    assert seeded.is_active is True


def test_run_list_shows_the_real_site_form(client, db) -> None:
    content = client.get(reverse("runs:list")).content.decode()

    assert "Evaluate a real website" in content
    assert 'name="start_url"' in content
