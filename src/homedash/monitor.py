"""Runs the configured checks on a timer in a background thread.

The UI (or a CLI) reads results via `get_results()`, which returns a
snapshot dict of name -> CheckResult. All state is protected by a lock so
it's safe to read from the Tkinter main thread while the monitor thread is
writing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .checks import BaseCheck, HomeAssistantCheck, InternetCheck, ProxmoxCheck, RouterCheck
from .models import CheckResult

logger = logging.getLogger(__name__)


def build_checks(config: dict[str, Any]) -> list[BaseCheck]:
    """Instantiate one check per enabled section of the config."""
    checks: list[BaseCheck] = []

    internet_cfg = config.get("internet", {}) or {}
    checks.append(InternetCheck(internet_cfg))

    ha_cfg = config.get("home_assistant", {}) or {}
    if ha_cfg.get("enabled", True):
        checks.append(HomeAssistantCheck(ha_cfg))

    pve_cfg = config.get("proxmox", {}) or {}
    if pve_cfg.get("enabled", True):
        checks.append(ProxmoxCheck(pve_cfg))

    router_cfg = config.get("router", {}) or {}
    if router_cfg.get("enabled", True):
        checks.append(RouterCheck(router_cfg))

    return checks


class Monitor:
    def __init__(self, config: dict[str, Any], checks: list[BaseCheck] | None = None):
        self.config = config
        self.checks = checks if checks is not None else build_checks(config)
        self.refresh_interval = config.get("refresh_interval_seconds", 60)

        self._lock = threading.Lock()
        self._results: dict[str, CheckResult] = {
            check.name: CheckResult.unknown(check.name) for check in self.checks
        }
        self._stop_event = threading.Event()
        # Set to wake the loop early, either to stop or to run a refresh
        # right now instead of waiting out the rest of the interval.
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None

    def run_once(self) -> dict[str, CheckResult]:
        """Run every check synchronously once and update stored results."""
        for check in self.checks:
            try:
                result = check.run()
            except Exception as exc:  # a check misbehaved and raised anyway
                logger.exception("Check %s raised unexpectedly", check.name)
                result = CheckResult.from_exception(check.name, exc)
            with self._lock:
                self._results[check.name] = result
        return self.get_results()

    def get_results(self) -> dict[str, CheckResult]:
        with self._lock:
            return dict(self._results)

    def request_refresh(self) -> None:
        """Wake the background loop immediately instead of waiting out the
        rest of the refresh interval. Safe to call from any thread (e.g.
        the UI's manual refresh button) - just sets an event, doesn't block
        or run checks itself.
        """
        self._wake_event.set()

    def start(self) -> None:
        """Start the background polling loop (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._loop, name="homedash-monitor", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._wake_event.wait(self.refresh_interval)
            self._wake_event.clear()
