from homedash.checks.base import BaseCheck
from homedash.models import CheckResult, Status
from homedash.monitor import Monitor, build_checks


class StubCheck(BaseCheck):
    name = "Stub"

    def __init__(self, status=Status.OK, raise_error=False):
        self._status = status
        self._raise_error = raise_error
        self.call_count = 0

    def run(self):
        self.call_count += 1
        if self._raise_error:
            raise RuntimeError("boom")
        return CheckResult(name=self.name, status=self._status, summary="stub result")


def test_run_once_updates_results():
    check = StubCheck()
    monitor = Monitor(config={}, checks=[check])

    results = monitor.run_once()

    assert results["Stub"].status == Status.OK
    assert check.call_count == 1


def test_run_once_survives_check_raising():
    check = StubCheck(raise_error=True)
    monitor = Monitor(config={}, checks=[check])

    results = monitor.run_once()

    assert results["Stub"].status == Status.ERROR
    assert "boom" in results["Stub"].error


def test_results_start_unknown_before_first_run():
    check = StubCheck()
    monitor = Monitor(config={}, checks=[check])

    results = monitor.get_results()

    assert results["Stub"].status == Status.UNKNOWN


def test_start_and_stop_background_loop():
    check = StubCheck()
    monitor = Monitor(config={"refresh_interval_seconds": 0.05}, checks=[check])

    monitor.start()
    try:
        monitor._stop_event.wait(0.3)
    finally:
        monitor.stop(timeout=2)

    assert check.call_count >= 1


def test_build_checks_respects_enabled_flags():
    config = {
        "internet": {},
        "home_assistant": {"enabled": False, "base_url": "http://ha", "token": "t"},
        "proxmox": {"enabled": False, "host": "pve", "token_id": "x", "token_secret": "y"},
        "router": {"enabled": False, "host": "10.0.0.1"},
    }

    checks = build_checks(config)

    names = {c.name for c in checks}
    assert names == {"Internet"}
