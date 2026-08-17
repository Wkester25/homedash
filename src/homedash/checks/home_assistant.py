"""Home Assistant vitals: API reachability + any entities stuck unavailable."""

from __future__ import annotations

from typing import Any

import requests

from ..models import CheckResult, Status
from .base import BaseCheck


class HomeAssistantCheck(BaseCheck):
    name = "Home Assistant"

    def __init__(self, config: dict[str, Any]):
        self.base_url: str = config["base_url"].rstrip("/")
        self.token: str = config.get("token", "")
        self.verify_ssl: bool = config.get("verify_ssl", True)
        self.timeout: int = config.get("timeout_seconds", 5)
        self.check_entities: bool = config.get("check_entities", True)
        self.ignore_entities: set[str] = set(config.get("ignore_entities", []) or [])

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def run(self) -> CheckResult:
        details: dict[str, Any] = {}

        try:
            resp = requests.get(
                f"{self.base_url}/api/",
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"Unreachable - {exc}",
                error=str(exc),
            )

        if resp.status_code == 401:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary="Unauthorized - check your long-lived access token",
            )
        if resp.status_code != 200:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"API returned HTTP {resp.status_code}",
            )

        details["api_message"] = resp.json().get("message")

        unavailable: list[dict[str, str]] = []
        if self.check_entities:
            unavailable, entity_error = self._fetch_unavailable_entities()
            details["unavailable_entities"] = unavailable
            if entity_error:
                details["entity_check_error"] = entity_error

        if unavailable:
            names = ", ".join(e["entity_id"] for e in unavailable[:5])
            more = f" (+{len(unavailable) - 5} more)" if len(unavailable) > 5 else ""
            return CheckResult(
                name=self.name,
                status=Status.WARN,
                summary=f"Up, but {len(unavailable)} entities unavailable: {names}{more}",
                details=details,
            )

        return CheckResult(
            name=self.name,
            status=Status.OK,
            summary="Up - API responding, all entities reporting",
            details=details,
        )

    def _fetch_unavailable_entities(self) -> tuple[list[dict[str, str]], str | None]:
        try:
            resp = requests.get(
                f"{self.base_url}/api/states",
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            return [], str(exc)

        bad = []
        for entity in resp.json():
            entity_id = entity.get("entity_id", "")
            state = entity.get("state")
            if entity_id in self.ignore_entities:
                continue
            if state in ("unavailable", "unknown"):
                bad.append({"entity_id": entity_id, "state": state})
        return bad, None
