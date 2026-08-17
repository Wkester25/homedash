"""Common interface every vitals check implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CheckResult


class BaseCheck(ABC):
    """A single named vitals check.

    Subclasses implement `run()` and should never let exceptions escape it -
    catch anything unexpected and return a CheckResult with Status.ERROR
    instead, so one broken check can't take down the whole monitor loop.
    The Monitor also wraps calls defensively, but well-behaved checks report
    their own failures with useful context (host, timeout, etc).
    """

    #: Short display name shown on the dashboard tile.
    name: str = "check"

    @abstractmethod
    def run(self) -> CheckResult:
        """Run the check once and return its result. Should not raise."""
        raise NotImplementedError
