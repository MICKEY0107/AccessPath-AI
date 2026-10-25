from __future__ import annotations

from engine.pacing import ProcessWideCallPacer


def test_process_wide_pacer_enforces_interval_across_new_clients() -> None:
    clock = [0.0]
    sleeps: list[float] = []

    def monotonic() -> float:
        return clock[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    provider = "test-provider-cross-instance"
    ProcessWideCallPacer.wait_for_turn(
        provider=provider,
        min_interval_seconds=20,
        sleep=sleep,
        monotonic=monotonic,
    )

    clock[0] = 5.0
    ProcessWideCallPacer.wait_for_turn(
        provider=provider,
        min_interval_seconds=20,
        sleep=sleep,
        monotonic=monotonic,
    )

    assert sleeps == [15.0]
