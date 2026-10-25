from apps.runs.tasks import health_check


def test_health_check_task_returns_expected_contract():
    assert health_check() == {"status": "ok"}
