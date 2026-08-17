"""Pure formatting helpers for the dashboard UI, kept separate from Tkinter
so they're testable without a display."""

from __future__ import annotations

from ..models import CheckResult, Status

STATUS_COLORS = {
    Status.OK: "#2e7d32",  # green
    Status.WARN: "#f9a825",  # amber
    Status.ERROR: "#c62828",  # red
    Status.UNKNOWN: "#616161",  # gray
}

STATUS_LABELS = {
    Status.OK: "OK",
    Status.WARN: "WARN",
    Status.ERROR: "ERROR",
    Status.UNKNOWN: "...",
}


def status_color(status: Status) -> str:
    return STATUS_COLORS.get(status, STATUS_COLORS[Status.UNKNOWN])


def status_label(status: Status) -> str:
    return STATUS_LABELS.get(status, "?")


def format_last_checked(result: CheckResult) -> str:
    return result.checked_at.strftime("%H:%M:%S")


def format_detail_lines(result: CheckResult) -> list[str]:
    """Turn a CheckResult's details dict into readable lines for a popup."""
    lines: list[str] = [result.summary, ""]
    details = result.details

    if "vms" in details:
        lines.append("Guests:")
        for vm in details["vms"]:
            cpu = f"{vm['cpu'] * 100:.0f}%" if vm.get("cpu") is not None else "n/a"
            mem = _format_bytes(vm.get("mem_bytes"))
            lines.append(f"  [{vm['status'].upper():7}] {vm['name']} ({vm['type']}) cpu={cpu} mem={mem}")
        if details.get("node_errors"):
            lines.append("")
            lines.append("Node errors:")
            for node, err in details["node_errors"].items():
                lines.append(f"  {node}: {err}")

    if "unavailable_entities" in details:
        entities = details["unavailable_entities"]
        if entities:
            lines.append("Unavailable entities:")
            for e in entities:
                lines.append(f"  {e['entity_id']}: {e['state']}")

    if "flagged_log_lines" in details:
        flagged = details["flagged_log_lines"]
        if flagged:
            lines.append("Flagged log lines:")
            lines.extend(f"  {line}" for line in flagged)
        elif "log_error" not in details:
            lines.append("No error-like lines in recent logs.")

    if "speedtest" in details and details["speedtest"]:
        st = details["speedtest"]
        lines.append("")
        if st.get("error"):
            lines.append(f"Speed test error: {st['error']}")
        else:
            cached = " (cached)" if st.get("cached") else ""
            lines.append(
                f"Speed test{cached}: {st['download_mbps']:.1f} Mbps down / "
                f"{st['upload_mbps']:.1f} Mbps up, {st['ping_ms']:.0f} ms via {st.get('server')}"
            )

    if result.error:
        lines.append("")
        lines.append(f"Error: {result.error}")

    return lines


def _format_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}PB"
