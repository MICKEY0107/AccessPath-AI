from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

from engine.contracts import ActionKind, ProposedActionV1
from engine.executor import KeyboardExecutor


def test_type_replaces_the_focused_value_with_keyboard_only_input() -> None:
    keyboard = Mock()
    page = SimpleNamespace(keyboard=keyboard)
    executor = object.__new__(KeyboardExecutor)

    executor._perform_action(
        page,
        ProposedActionV1(
            action=ActionKind.TYPE,
            value="Asha Test",
            target_hint="name",
            purpose="enter the synthetic name",
        ),
    )

    assert keyboard.mock_calls == [call.press("Control+A"), call.type("Asha Test")]


def test_screenshot_failure_is_recorded_without_aborting_the_run() -> None:
    page = Mock()
    page.screenshot.side_effect = RuntimeError("capture unavailable")
    artifact_store = Mock()
    artifact_store.screenshot_path.return_value = Path("evidence.png")
    executor = object.__new__(KeyboardExecutor)
    executor.artifact_store = artifact_store
    executor._pending_evidence_events = []

    artifact = executor._capture_screenshot(page, 1, "before")

    assert artifact is None
    assert executor._consume_evidence_events() == [
        "SCREENSHOT_CAPTURE_FAILED before RUNTIMEERROR"
    ]
    assert page.screenshot.call_count == 2
    artifact_store.describe.assert_not_called()


def test_screenshot_capture_retries_once_before_recording_a_gap() -> None:
    page = Mock()
    page.screenshot.side_effect = [RuntimeError("capture unavailable"), None]
    artifact_store = Mock()
    artifact_store.screenshot_path.return_value = Path("evidence.png")
    expected = Mock()
    artifact_store.describe.return_value = expected
    executor = object.__new__(KeyboardExecutor)
    executor.artifact_store = artifact_store
    executor._pending_evidence_events = []

    artifact = executor._capture_screenshot(page, 1, "after")

    assert artifact is expected
    assert executor._consume_evidence_events() == []
    assert page.screenshot.call_count == 2
