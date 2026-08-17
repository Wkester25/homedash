"""Proxmox VE vitals: node health plus every VM/LXC container's status."""

from __future__ import annotations

from typing import Any

import requests
import urllib3

from ..models import CheckResult, Status
from .base import BaseCheck


class ProxmoxCheck(BaseCheck):
    name = "Proxmox"

    def __init__(self, config: dict[str, Any]):
        self.host: str = config["host"]
        self.port: int = config.get("port", 8006)
        self.token_id: str = config["token_id"]
        self.token_secret: str = config.get("token_secret", "")
        self.verify_ssl: bool = config.get("verify_ssl", False)
        self.timeout: int = config.get("timeout_seconds", 5)
        self.configured_nodes: list[str] = config.get("nodes", []) or []
        self.ignore_vms: set[int] = {int(v) for v in (config.get("ignore_vms", []) or [])}

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}/api2/json"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}"}

    def _get(self, path: str) -> Any:
        resp = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def run(self) -> CheckResult:
        try:
            nodes = self._get("/nodes")
        except requests.RequestException as exc:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"Unreachable - {exc}",
                error=str(exc),
            )

        node_names = self.configured_nodes or [n["node"] for n in nodes]
        node_status_by_name = {n["node"]: n.get("status") for n in nodes}

        offline_nodes: list[str] = []
        vms: list[dict[str, Any]] = []
        node_errors: dict[str, str] = {}

        for node_name in node_names:
            if node_status_by_name.get(node_name, "online") != "online":
                offline_nodes.append(node_name)
                continue
            try:
                vms.extend(self._collect_guests(node_name, "qemu", "VM"))
                vms.extend(self._collect_guests(node_name, "lxc", "LXC"))
            except requests.RequestException as exc:
                node_errors[node_name] = str(exc)

        stopped = [
            v for v in vms if v["status"] != "running" and v["vmid"] not in self.ignore_vms
        ]

        details: dict[str, Any] = {
            "nodes": node_names,
            "offline_nodes": offline_nodes,
            "node_errors": node_errors,
            "vms": vms,
        }

        if offline_nodes:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"Node(s) offline: {', '.join(offline_nodes)}",
                details=details,
            )

        if node_errors:
            return CheckResult(
                name=self.name,
                status=Status.ERROR,
                summary=f"Failed to query node(s): {', '.join(node_errors)}",
                details=details,
            )

        if stopped:
            names = ", ".join(f"{v['name']} ({v['type']})" for v in stopped[:5])
            more = f" (+{len(stopped) - 5} more)" if len(stopped) > 5 else ""
            return CheckResult(
                name=self.name,
                status=Status.WARN,
                summary=f"{len(stopped)} guest(s) not running: {names}{more}",
                details=details,
            )

        return CheckResult(
            name=self.name,
            status=Status.OK,
            summary=f"{len(node_names)} node(s), {len(vms)} guest(s) all running",
            details=details,
        )

    def _collect_guests(self, node_name: str, kind: str, label: str) -> list[dict[str, Any]]:
        guests = self._get(f"/nodes/{node_name}/{kind}")
        result = []
        for g in guests:
            result.append(
                {
                    "vmid": g["vmid"],
                    "name": g.get("name", str(g["vmid"])),
                    "type": label,
                    "node": node_name,
                    "status": g.get("status", "unknown"),
                    "cpu": g.get("cpu"),
                    "mem_bytes": g.get("mem"),
                    "maxmem_bytes": g.get("maxmem"),
                    "uptime_seconds": g.get("uptime"),
                }
            )
        return result
