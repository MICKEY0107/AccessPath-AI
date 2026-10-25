from engine.contracts import ActionKind, ElementEvidenceV1, ProposedActionV1
from engine.policy import KeyboardActionPolicy


def test_policy_rejects_typing_when_focused_element_is_not_editable():
    decision = KeyboardActionPolicy().decide(
        ProposedActionV1(action=ActionKind.TYPE, value="Asha", purpose="enter name"),
        ElementEvidenceV1(
            fingerprint="button-continue", role="button", name="Continue", editable=False
        ),
        prior_same_code_rejections=0,
    )

    assert decision.outcome == "rejected"
    assert decision.code == "TYPE_TARGET_NOT_EDITABLE"
