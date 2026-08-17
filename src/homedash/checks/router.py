"""Router vitals: reachability plus a scan of recent log lines for errors.

Log fetching is generic-by-design: it SSHes in and runs whatever command
your router's firmware exposes for viewing logs (see config.example.yaml
for presets for OpenWrt/DD-WRT, pfSense/OPNsense, and plain Linux gateways),
then flags any line matching one of your configured error patterns.
"""

from __future__ import annotations

from typing import Any

from ..models import CheckResult, Status
from ..net_utils import ping
from .base import BaseCheck

try:
    import paramiko
except ImportError:  # pragma: no cover - exercised only when dependency missing
    paramiko = None


class RouterCheck(BaseCheck):
    name = "Router"

    def __init__(self, config: dict[str, Any]):
        self.host: str = config["host"]
        self.ping_check: bool = config.get("ping_check", True)
        self.ping_timeout: int = config.get("ping_timeout_seconds", 2)

        ssh_config = config.get("ssh", {}) or {}
        self.ssh_enabled: bool = ssh_config.get("enabled", False)
        self.ssh_port: int = ssh_config.get("port", 22)
        self.ssh_username: str = ssh_config.get("username", "root")
        self.ssh_password: str | None = ssh_config.get("password")
        self.ssh_key_filename: str | None = ssh_config.get("key_filename")
        self.log_command: str = ssh_config.get("log_command", "logread | tail -n 200")
        self.error_patterns: list[str] = [
            p.lower() for p in (ssh_config.get("error_patterns", []) or [])
        ]
        self.ignore_patterns: list[str] = [
            p.lower() for p in (ssh_config.get("ignore_patterns", []) or [])
        ]
        self.max_flagged_lines: int = ssh_config.get("max_flagged_lines", 20)
        self.ssh_timeout: int = config.get("ssh_timeout_seconds", 8)

    def run(self) -> CheckResult:
        details: dict[str, Any] = {}

        if self.ping_check:
            ping_result = ping(self.host, count=2, timeout_seconds=self.ping_timeout)
            details["ping"] = {
                "reachable": ping_result.reachable,
                "avg_latency_ms": ping_result.avg_latency_ms,
            }
            if not ping_result.reachable:
                return CheckResult(
                    name=self.name,
                    status=Status.ERROR,
                    summary=f"Router unreachable at {self.host}",
                    details=details,
                )

        if not self.ssh_enabled:
            return CheckResult(
                name=self.name,
                status=Status.OK,
                summary="Router reachable (log check disabled)",
                details=details,
            )

        flagged, log_error = self._check_logs()
        details["flagged_log_lines"] = flagged
        if log_error:
            details["log_error"] = log_error
            return CheckResult(
                name=self.name,
                status=Status.WARN,
                summary=f"Reachable, but couldn't read logs: {log_error}",
                details=details,
            )

        if flagged:
            return CheckResult(
                name=self.name,
                status=Status.WARN,
                summary=f"Reachable - {len(flagged)} error-like line(s) in recent logs",
                details=details,
            )

        return CheckResult(
            name=self.name,
            status=Status.OK,
            summary="Reachable - no errors in recent logs",
            details=details,
        )

    def _check_logs(self) -> tuple[list[str], str | None]:
        if paramiko is None:
            return [], "paramiko not installed"
        if not self.error_patterns:
            return [], None

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                port=self.ssh_port,
                username=self.ssh_username,
                password=self.ssh_password,
                key_filename=self.ssh_key_filename,
                timeout=self.ssh_timeout,
                allow_agent=False,
                look_for_keys=self.ssh_key_filename is not None,
            )
            _stdin, stdout, stderr = client.exec_command(self.log_command, timeout=self.ssh_timeout)
            output = stdout.read().decode(errors="replace")
            err_output = stderr.read().decode(errors="replace")
        except Exception as exc:  # paramiko raises many distinct exception types
            return [], str(exc)
        finally:
            client.close()

        if not output.strip() and err_output.strip():
            return [], err_output.strip()[:300]

        flagged = []
        for line in output.splitlines():
            lower = line.lower()
            if any(ig in lower for ig in self.ignore_patterns):
                continue
            if any(pat in lower for pat in self.error_patterns):
                flagged.append(line.strip())

        return flagged[-self.max_flagged_lines :], None
