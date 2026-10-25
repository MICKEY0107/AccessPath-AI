import pytest

from engine.contracts import TargetPolicyV1
from engine.target_policy import TargetPolicy


@pytest.fixture
def wikipedia_policy() -> TargetPolicy:
    return TargetPolicy(
        TargetPolicyV1.model_validate(
            {
                "navigation_origins": ["https://en.wikipedia.org"],
                "resource_origins": [
                    "https://en.wikipedia.org",
                    "https://upload.wikimedia.org",
                ],
                "navigation_path_prefixes": ["/wiki/", "/w/index.php"],
                "allowed_methods": ["GET", "HEAD", "OPTIONS"],
            }
        )
    )


def test_target_policy_allows_approved_read_only_navigation(wikipedia_policy: TargetPolicy):
    decision = wikipedia_policy.decide_request(
        "https://en.wikipedia.org/wiki/Web_accessibility",
        method="GET",
        is_navigation=True,
    )

    assert decision.allowed is True
    assert decision.code == "REQUEST_ALLOWED"


@pytest.mark.parametrize(
    ("url", "method", "expected_code"),
    [
        ("https://example.org/wiki/Web_accessibility", "GET", "NAVIGATION_ORIGIN_NOT_ALLOWED"),
        ("https://en.wikipedia.org/w/api.php", "GET", "NAVIGATION_PATH_NOT_ALLOWED"),
        ("https://en.wikipedia.org/wiki/Web_accessibility", "POST", "REQUEST_METHOD_NOT_ALLOWED"),
    ],
)
def test_target_policy_blocks_navigation_outside_the_manifest(
    wikipedia_policy: TargetPolicy,
    url: str,
    method: str,
    expected_code: str,
):
    decision = wikipedia_policy.decide_request(url, method=method, is_navigation=True)

    assert decision.allowed is False
    assert decision.code == expected_code


def test_target_policy_allows_reviewed_static_resource_origin(wikipedia_policy: TargetPolicy):
    decision = wikipedia_policy.decide_request(
        "https://upload.wikimedia.org/example.svg",
        method="GET",
        is_navigation=False,
    )

    assert decision.allowed is True


def test_target_policy_blocks_unreviewed_resource_origin(wikipedia_policy: TargetPolicy):
    decision = wikipedia_policy.decide_request(
        "https://tracking.example/pixel.gif",
        method="GET",
        is_navigation=False,
    )

    assert decision.allowed is False
    assert decision.code == "RESOURCE_ORIGIN_NOT_ALLOWED"
