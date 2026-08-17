"""Small shared network helpers used by more than one check."""

from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass


@dataclass
class PingResult:
    reachable: bool
    packet_loss_pct: float | None = None
    avg_latency_ms: float | None = None
    raw_error: str | None = None


_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*packet loss")
# Linux/macOS: "rtt min/avg/max/mdev = 0.020/0.025/0.030/0.005 ms"
_RTT_RE = re.compile(r"=\s*[\d.]+/([\d.]+)/[\d.]+")
# Windows: "Average = 12ms"
_WIN_AVG_RE = re.compile(r"Average\s*=\s*(\d+)\s*ms")


def ping(host: str, count: int = 3, timeout_seconds: int = 2) -> PingResult:
    """Ping `host` using the system `ping` binary.

    Shells out rather than crafting raw ICMP sockets so this works without
    root/CAP_NET_RAW on Linux (which a plain socket-based ping needs).
    """
    is_windows = platform.system().lower() == "windows"
    if is_windows:
        cmd = ["ping", "-n", str(count), "-w", str(timeout_seconds * 1000), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_seconds), host]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds * count + 5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return PingResult(reachable=False, raw_error=str(exc))

    output = proc.stdout + proc.stderr

    if proc.returncode != 0:
        loss_match = _LOSS_RE.search(output)
        loss = float(loss_match.group(1)) if loss_match else 100.0
        return PingResult(reachable=False, packet_loss_pct=loss, raw_error=output.strip()[-500:])

    loss_match = _LOSS_RE.search(output)
    loss = float(loss_match.group(1)) if loss_match else 0.0

    latency = None
    rtt_match = _RTT_RE.search(output)
    if rtt_match:
        latency = float(rtt_match.group(1))
    else:
        win_match = _WIN_AVG_RE.search(output)
        if win_match:
            latency = float(win_match.group(1))

    return PingResult(reachable=loss < 100.0, packet_loss_pct=loss, avg_latency_ms=latency)
