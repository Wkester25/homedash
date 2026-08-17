from homedash.models import CheckResult, Status
from homedash.ui.formatting import format_detail_lines, status_color, status_label


def test_status_color_and_label_cover_all_statuses():
    for status in Status:
        assert status_color(status).startswith("#")
        assert status_label(status)


def test_format_detail_lines_includes_vms():
    result = CheckResult(
        name="Proxmox",
        status=Status.WARN,
        summary="1 guest not running",
        details={
            "vms": [
                {"vmid": 100, "name": "ha", "type": "VM", "status": "stopped", "cpu": None, "mem_bytes": None},
            ],
            "node_errors": {},
        },
    )

    lines = format_detail_lines(result)

    assert any("ha" in line and "STOPPED" in line for line in lines)


def test_format_detail_lines_includes_flagged_logs():
    result = CheckResult(
        name="Router",
        status=Status.WARN,
        summary="errors found",
        details={"flagged_log_lines": ["auth FAILED for admin"]},
    )

    lines = format_detail_lines(result)

    assert any("auth FAILED" in line for line in lines)


def test_format_detail_lines_no_flagged_logs_says_so():
    result = CheckResult(
        name="Router",
        status=Status.OK,
        summary="all good",
        details={"flagged_log_lines": []},
    )

    lines = format_detail_lines(result)

    assert any("no error-like lines" in line.lower() for line in lines)
