from unittest.mock import MagicMock, patch

from homedash.checks.router import RouterCheck
from homedash.models import Status
from homedash.net_utils import PingResult


def make_check(**overrides):
    config = {
        "host": "192.168.1.1",
        "ping_check": True,
        "ping_timeout_seconds": 2,
        "ssh": {
            "enabled": True,
            "port": 22,
            "username": "root",
            "password": "pw",
            "key_filename": None,
            "log_command": "logread",
            "error_patterns": ["error", "fail"],
            "ignore_patterns": [],
            "max_flagged_lines": 20,
        },
    }
    config.update({k: v for k, v in overrides.items() if k != "ssh"})
    if "ssh" in overrides:
        config["ssh"].update(overrides["ssh"])
    return RouterCheck(config)


@patch("homedash.checks.router.ping")
def test_unreachable_router_is_error(mock_ping):
    mock_ping.return_value = PingResult(reachable=False)
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR


@patch("homedash.checks.router.paramiko")
@patch("homedash.checks.router.ping")
def test_clean_logs_is_ok(mock_ping, mock_paramiko):
    mock_ping.return_value = PingResult(reachable=True, avg_latency_ms=1.0)

    client = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = b"Aug 17 12:00:00 router: link up\nAug 17 12:00:05 router: dhcp lease renewed\n"
    stderr = MagicMock()
    stderr.read.return_value = b""
    client.exec_command.return_value = (MagicMock(), stdout, stderr)
    mock_paramiko.SSHClient.return_value = client

    check = make_check()
    result = check.run()

    assert result.status == Status.OK
    assert result.details["flagged_log_lines"] == []


@patch("homedash.checks.router.paramiko")
@patch("homedash.checks.router.ping")
def test_error_lines_trigger_warn(mock_ping, mock_paramiko):
    mock_ping.return_value = PingResult(reachable=True, avg_latency_ms=1.0)

    client = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = (
        b"Aug 17 12:00:00 router: link up\n"
        b"Aug 17 12:00:05 router: authentication FAILED for admin\n"
    )
    stderr = MagicMock()
    stderr.read.return_value = b""
    client.exec_command.return_value = (MagicMock(), stdout, stderr)
    mock_paramiko.SSHClient.return_value = client

    check = make_check()
    result = check.run()

    assert result.status == Status.WARN
    assert len(result.details["flagged_log_lines"]) == 1
    assert "FAILED" in result.details["flagged_log_lines"][0]


@patch("homedash.checks.router.paramiko")
@patch("homedash.checks.router.ping")
def test_ignore_patterns_suppress_matches(mock_ping, mock_paramiko):
    mock_ping.return_value = PingResult(reachable=True, avg_latency_ms=1.0)

    client = MagicMock()
    stdout = MagicMock()
    stdout.read.return_value = b"Aug 17 12:00:05 router: known benign fail-safe triggered\n"
    stderr = MagicMock()
    stderr.read.return_value = b""
    client.exec_command.return_value = (MagicMock(), stdout, stderr)
    mock_paramiko.SSHClient.return_value = client

    check = make_check(ssh={"ignore_patterns": ["fail-safe"]})
    result = check.run()

    assert result.status == Status.OK


@patch("homedash.checks.router.ping")
def test_ssh_disabled_skips_log_check(mock_ping):
    mock_ping.return_value = PingResult(reachable=True, avg_latency_ms=1.0)
    check = make_check(ssh={"enabled": False})

    result = check.run()

    assert result.status == Status.OK
    assert "flagged_log_lines" not in result.details


@patch("homedash.checks.router.paramiko")
@patch("homedash.checks.router.ping")
def test_ssh_connection_error_is_warn(mock_ping, mock_paramiko):
    mock_ping.return_value = PingResult(reachable=True, avg_latency_ms=1.0)
    client = MagicMock()
    client.connect.side_effect = OSError("connection refused")
    mock_paramiko.SSHClient.return_value = client

    check = make_check()
    result = check.run()

    assert result.status == Status.WARN
    assert "logs" in result.summary.lower()
