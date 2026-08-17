"""Internet connectivity, DNS, and periodic speed test."""

from __future__ import annotations

import socket
import time
from typing import Any

from ..models import CheckResult, Status
from ..net_utils import ping
from .base import BaseCheck


class InternetCheck(BaseCheck):
    name = "Internet"

    def __init__(self, config: dict[str, Any]):
        self.ping_host: str = config.get("ping_host", "1.1.1.1")
        self.ping_count: int = config.get("ping_count", 3)
        self.ping_timeout: int = config.get("ping_timeout_seconds", 2)
        self.dns_check_host: str = config.get("dns_check_host", "google.com")
        self.run_speedtest: bool = config.get("run_speedtest", True)
        self.speedtest_interval_seconds: float = (
            config.get("speedtest_interval_minutes", 30) * 60
        )

        self._last_speedtest_at: float = 0.0
        self._last_speedtest_result: dict[str, Any] | None = None

    def run(self) -> CheckResult:
        details: dict[str, Any] = {}

        ping_result = ping(self.ping_host, count=self.ping_count, timeout_seconds=self.ping_timeout)
        details["ping"] = {
            "host": self.ping_host,
            "reachable": ping_result.reachable,
            "packet_loss_pct": ping_result.packet_loss_pct,
            "avg_latency_ms": ping_result.avg_latency_ms,
        }

        if not ping_result.reachable:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"No internet - can't reach {self.ping_host}",
                details=details,
            )

        dns_ok, dns_error = self._check_dns()
        details["dns"] = {"host": self.dns_check_host, "ok": dns_ok, "error": dns_error}

        if not dns_ok:
            return CheckResult(
                name=self.name,
                status=Status.WARN,
                summary=f"Online, but DNS lookup for {self.dns_check_host} failed",
                details=details,
            )

        speed_summary = ""
        if self.run_speedtest:
            speed = self._maybe_run_speedtest()
            details["speedtest"] = speed
            if speed and speed.get("error"):
                speed_summary = " (speed test failed)"
            elif speed:
                cached_tag = " cached" if speed.get("cached") else ""
                speed_summary = (
                    f" - {speed['download_mbps']:.0f}/{speed['upload_mbps']:.0f} Mbps{cached_tag}"
                )

        latency = ping_result.avg_latency_ms
        latency_txt = f"{latency:.0f} ms" if latency is not None else "n/a"
        return CheckResult(
            name=self.name,
            status=Status.OK,
            summary=f"Online - {latency_txt} latency{speed_summary}",
            details=details,
        )

    def _check_dns(self) -> tuple[bool, str | None]:
        try:
            socket.getaddrinfo(self.dns_check_host, None)
            return True, None
        except socket.gaierror as exc:
            return False, str(exc)

    def _maybe_run_speedtest(self) -> dict[str, Any] | None:
        now = time.monotonic()
        if (
            self._last_speedtest_result is not None
            and now - self._last_speedtest_at < self.speedtest_interval_seconds
        ):
            cached = dict(self._last_speedtest_result)
            cached["cached"] = True
            return cached

        try:
            import speedtest
        except ImportError:
            return {"error": "speedtest-cli not installed"}

        try:
            st = speedtest.Speedtest(secure=True)
            st.get_best_server()
            download_bps = st.download()
            upload_bps = st.upload()
            result = {
                "download_mbps": download_bps / 1_000_000,
                "upload_mbps": upload_bps / 1_000_000,
                "ping_ms": st.results.ping,
                "server": st.results.server.get("sponsor"),
                "cached": False,
            }
        except Exception as exc:  # speedtest raises its own broad exceptions
            result = {"error": str(exc)}

        self._last_speedtest_at = now
        self._last_speedtest_result = result if "error" not in result else self._last_speedtest_result
        return result
