"""Shared data types used by every check and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Overall health of a single check."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class CheckResult:
    """Outcome of running one vitals check.

    `summary` is the short, human-readable line shown on the main dashboard
    tile. `details` is a free-form dict of extra data (per-VM status, log
    lines, speedtest numbers, ...) shown when a tile is opened/expanded.
    """

    name: str
    status: Status
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)
    error: str | None = None

    @classmethod
    def unknown(cls, name: str, message: str = "Not checked yet") -> "CheckResult":
        return cls(name=name, status=Status.UNKNOWN, summary=message)

    @classmethod
    def from_exception(cls, name: str, exc: Exception) -> "CheckResult":
        return cls(
            name=name,
            status=Status.ERROR,
            summary=f"Check failed: {exc}",
            error=repr(exc),
        )
