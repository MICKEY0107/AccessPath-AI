"""Journeys on real websites, added from the dashboard.

A real-site journey reuses the same fail-closed target policy as the reviewed
public pilot: only GET/HEAD/OPTIONS requests, no popups or downloads, navigation
limited to the site's own origin(s), and every action keyboard-only. Because
nothing is ever submitted with POST, logins, checkouts, and booking forms stop
safely rather than completing; read-only journeys (search, browse, find a page)
are what this mode can evaluate.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from pydantic import ValidationError

from engine.contracts import CompletionPolicyV1, TargetPolicyV1
from engine.target_policy import TargetPolicy, is_local_or_private_host

from .models import ExecutionMode, Journey

REAL_SITE_SOURCE = "user"
TYPED_VALUE_KEY = "text_to_type"
REAL_SITE_USER_AGENT = "AccessPathAI-local/0.2 keyboard-accessibility-evaluator"


def host_is_public(hostname: str) -> bool:
    """True only when every address the host resolves to is publicly routable."""
    if is_local_or_private_host(hostname):
        return False
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(hostname, None)}
    except (socket.gaierror, UnicodeError):
        return False
    try:
        return bool(addresses) and all(
            ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses
        )
    except ValueError:
        return False


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}".lower()


class RealSiteJourneyForm(forms.Form):
    name = forms.CharField(max_length=120, label="Journey name")
    start_url = forms.URLField(
        max_length=500,
        label="Start page",
        assume_scheme="https",
        help_text="The page the evaluation opens first, for example https://www.example.org/.",
    )
    goal = forms.CharField(
        min_length=10,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Goal",
        help_text="What a keyboard user is trying to do, in plain words.",
    )
    success_url_contains = forms.CharField(
        max_length=256,
        required=False,
        label="Success when the address contains",
        help_text="For example /contact or search=accessibility. Leave blank if not needed.",
    )
    success_text = forms.CharField(
        max_length=256,
        required=False,
        label="Success when the page shows this text",
        help_text="Text that only appears once the goal is reached. Not case sensitive.",
    )
    text_to_type = forms.CharField(
        max_length=256,
        required=False,
        label="Text the evaluator may type",
        help_text="Optional, for example a search term. Never enter passwords or personal data.",
    )
    extra_origins = forms.CharField(
        required=False,
        label="Other addresses the journey may visit",
        help_text="Optional. One per line, such as https://shop.example.org.",
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    max_actions = forms.IntegerField(
        min_value=5,
        max_value=100,
        initial=40,
        label="Maximum keyboard actions",
    )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if Journey.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A journey with this name already exists.")
        return name

    def clean_start_url(self) -> str:
        url = self.cleaned_data["start_url"]
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise forms.ValidationError("Use an http or https address.")
        if parsed.username or parsed.password:
            raise forms.ValidationError("Do not put a username or password in the address.")
        if not settings.ALLOW_PRIVATE_NETWORKS and not host_is_public(parsed.hostname):
            raise forms.ValidationError(
                "This address is not a reachable public website, or it points to a private "
                "or local network, which real-site evaluations are not allowed to open."
            )
        return url

    def clean_extra_origins(self) -> list[str]:
        origins: list[str] = []
        for line in re.split(r"[\s,]+", self.cleaned_data.get("extra_origins", "")):
            if not line:
                continue
            parsed = urlparse(line if "://" in line else f"https://{line}")
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise forms.ValidationError(f"{line} is not a valid web address.")
            if not settings.ALLOW_PRIVATE_NETWORKS and not host_is_public(parsed.hostname):
                raise forms.ValidationError(f"{line} is not a reachable public website.")
            origin = f"{parsed.scheme}://{parsed.netloc}".lower()
            if origin not in origins:
                origins.append(origin)
        if len(origins) > 9:
            raise forms.ValidationError("List at most 9 other addresses.")
        return origins

    def clean(self) -> dict:
        cleaned = super().clean()
        if not (cleaned.get("success_url_contains") or cleaned.get("success_text")):
            raise forms.ValidationError(
                "Add at least one success check, so a run can only pass when the goal is "
                "really reached."
            )
        return cleaned

    def create_journey(self) -> Journey:
        data = self.cleaned_data
        start_url = data["start_url"]
        origins = [origin_of(start_url), *data["extra_origins"]]
        origins = list(dict.fromkeys(origins))
        target_policy = TargetPolicyV1(
            navigation_origins=origins,
            resource_origins=origins,
            navigation_path_prefixes=["/"],
            allow_any_resource_origin=True,
            max_pages=1,
            max_actions=data["max_actions"],
            total_timeout_ms=900_000,
            no_progress_limit=6,
            user_agent=REAL_SITE_USER_AGENT,
        )
        signals = []
        if data.get("success_url_contains"):
            signals.append(
                {
                    "id": "success_address",
                    "type": "url_contains",
                    "expected": data["success_url_contains"].strip(),
                    "case_sensitive": False,
                }
            )
        if data.get("success_text"):
            signals.append(
                {
                    "id": "success_text",
                    "type": "text_present",
                    "expected": " ".join(data["success_text"].split()),
                    "case_sensitive": False,
                }
            )
        try:
            completion_policy = CompletionPolicyV1.model_validate({"signals": signals})
            TargetPolicy(target_policy).validate_start_url(start_url)
        except (ValidationError, ValueError) as error:
            raise forms.ValidationError(f"The journey could not be built: {error}") from error

        synthetic_values = (
            {TYPED_VALUE_KEY: data["text_to_type"].strip()} if data.get("text_to_type") else {}
        )
        return Journey.objects.create(
            name=data["name"],
            goal=data["goal"].strip(),
            start_url=start_url,
            execution_mode=ExecutionMode.PUBLIC_READ_ONLY,
            allowed_origins=origins,
            completion_policy=completion_policy.model_dump(mode="json"),
            evaluation_config={
                "source": REAL_SITE_SOURCE,
                "journey_key": f"real-site-{re.sub(r'[^a-z0-9]+', '-', data['name'].lower())}",
                "target_policy": target_policy.model_dump(mode="json"),
                "planner": {
                    "kind": "gemini.v1",
                    # No scripted replay exists for an arbitrary site; a provider failure
                    # ends the run with its reason instead.
                    "allow_no_fallback": True,
                    "synthetic_values": synthetic_values,
                },
            },
        )
