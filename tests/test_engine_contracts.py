import pytest
from pydantic import ValidationError

from engine.contracts import (
    ActionKind,
    CompletionPolicyV1,
    ProposedActionV1,
    TargetPolicyV1,
)


def test_type_action_requires_value():
    action = ProposedActionV1(
        action=ActionKind.TYPE,
        value="Asha",
        target_hint="Name",
        purpose="enter synthetic name",
    )

    assert action.value == "Asha"


def test_completion_policy_accepts_a_level_one_heading_signal():
    policy = CompletionPolicyV1.model_validate(
        {
            "signals": [
                {"id": "url", "type": "url_path_equals", "expected": "/wiki/example"},
                {
                    "id": "heading",
                    "type": "element_present",
                    "locator": {"by": "heading", "value": "Example", "level": 1},
                },
            ]
        }
    )

    assert policy.signals[1].locator is not None
    assert policy.signals[1].locator.level == 1


def test_heading_completion_locator_requires_a_heading_level():
    with pytest.raises(ValidationError, match="heading locators require a level"):
        CompletionPolicyV1.model_validate(
            {
                "signals": [
                    {
                        "id": "heading",
                        "type": "element_present",
                        "locator": {"by": "heading", "value": "Example"},
                    }
                ]
            }
        )


def test_target_policy_rejects_origins_that_include_a_path():
    with pytest.raises(ValidationError, match="origins must not include a path"):
        TargetPolicyV1.model_validate(
            {
                "navigation_origins": ["https://example.com/wiki"],
                "resource_origins": ["https://example.com"],
                "navigation_path_prefixes": ["/wiki/"],
            }
        )


def test_target_policy_bounds_the_keyboard_action_budget():
    policy = TargetPolicyV1.model_validate(
        {
            "navigation_origins": ["https://example.com"],
            "resource_origins": ["https://example.com"],
            "navigation_path_prefixes": ["/"],
            "max_actions": 12,
        }
    )

    assert policy.max_actions == 12
