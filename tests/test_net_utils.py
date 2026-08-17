from unittest.mock import patch

from homedash.net_utils import ping


LINUX_SUCCESS = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=59 time=12.3 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=59 time=11.8 ms

--- 1.1.1.1 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1001ms
rtt min/avg/max/mdev = 11.800/12.050/12.300/0.250 ms
"""

LINUX_FAILURE = """PING 10.0.0.99 (10.0.0.99) 56(84) bytes of data.

--- 10.0.0.99 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2042ms
"""


def _fake_proc(stdout="", stderr="", returncode=0):
    class P:
        pass

    p = P()
    p.stdout = stdout
    p.stderr = stderr
    p.returncode = returncode
    return p


@patch("homedash.net_utils.platform.system", return_value="Linux")
@patch("homedash.net_utils.subprocess.run")
def test_ping_success_parses_loss_and_latency(mock_run, _mock_system):
    mock_run.return_value = _fake_proc(stdout=LINUX_SUCCESS, returncode=0)

    result = ping("1.1.1.1", count=2, timeout_seconds=2)

    assert result.reachable is True
    assert result.packet_loss_pct == 0.0
    assert result.avg_latency_ms == 12.05


@patch("homedash.net_utils.platform.system", return_value="Linux")
@patch("homedash.net_utils.subprocess.run")
def test_ping_failure_reports_unreachable(mock_run, _mock_system):
    mock_run.return_value = _fake_proc(stdout=LINUX_FAILURE, returncode=1)

    result = ping("10.0.0.99", count=3, timeout_seconds=2)

    assert result.reachable is False
    assert result.packet_loss_pct == 100.0


@patch("homedash.net_utils.subprocess.run", side_effect=FileNotFoundError("no ping binary"))
def test_ping_missing_binary_is_handled(_mock_run):
    result = ping("1.1.1.1")

    assert result.reachable is False
    assert "no ping binary" in result.raw_error
