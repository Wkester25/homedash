import socket
from unittest.mock import MagicMock, patch

from homedash.checks.internet import InternetCheck
from homedash.models import Status
from homedash.net_utils import PingResult


def make_check(**overrides):
    config = {
        "ping_host": "1.1.1.1",
        "ping_count": 2,
        "ping_timeout_seconds": 2,
        "dns_check_host": "google.com",
        "run_speedtest": False,
    }
    config.update(overrides)
    return InternetCheck(config)


@patch("homedash.checks.internet.ping")
def test_no_internet_when_ping_fails(mock_ping):
    mock_ping.return_value = PingResult(reachable=False, packet_loss_pct=100.0)
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR
    assert "internet" in result.summary.lower()


@patch("homedash.checks.internet.socket.getaddrinfo", side_effect=socket.gaierror("dns down"))
@patch("homedash.checks.internet.ping")
def test_dns_failure_is_warn(mock_ping, _mock_dns):
    mock_ping.return_value = PingResult(reachable=True, packet_loss_pct=0.0, avg_latency_ms=10.0)
    check = make_check()

    result = check.run()

    assert result.status == Status.WARN
    assert "dns" in result.summary.lower()


@patch("homedash.checks.internet.socket.getaddrinfo", return_value=[])
@patch("homedash.checks.internet.ping")
def test_online_and_dns_ok_is_ok(mock_ping, _mock_dns):
    mock_ping.return_value = PingResult(reachable=True, packet_loss_pct=0.0, avg_latency_ms=15.5)
    check = make_check()

    result = check.run()

    assert result.status == Status.OK
    assert "16 ms" in result.summary or "15" in result.summary


@patch("homedash.checks.internet.socket.getaddrinfo", return_value=[])
@patch("homedash.checks.internet.ping")
def test_speedtest_result_included_when_enabled(mock_ping, _mock_dns):
    mock_ping.return_value = PingResult(reachable=True, packet_loss_pct=0.0, avg_latency_ms=10.0)
    check = make_check(run_speedtest=True, speedtest_interval_minutes=30)

    fake_speedtest_module = MagicMock()
    instance = fake_speedtest_module.Speedtest.return_value
    instance.download.return_value = 100_000_000  # 100 Mbps
    instance.upload.return_value = 20_000_000  # 20 Mbps
    instance.results.ping = 8.0
    instance.results.server = {"sponsor": "TestISP"}

    with patch.dict("sys.modules", {"speedtest": fake_speedtest_module}):
        result = check.run()

    assert result.status == Status.OK
    speed = result.details["speedtest"]
    assert speed["download_mbps"] == 100.0
    assert speed["upload_mbps"] == 20.0
    assert speed["cached"] is False


@patch("homedash.checks.internet.socket.getaddrinfo", return_value=[])
@patch("homedash.checks.internet.ping")
def test_speedtest_is_cached_within_interval(mock_ping, _mock_dns):
    mock_ping.return_value = PingResult(reachable=True, packet_loss_pct=0.0, avg_latency_ms=10.0)
    check = make_check(run_speedtest=True, speedtest_interval_minutes=30)

    fake_speedtest_module = MagicMock()
    instance = fake_speedtest_module.Speedtest.return_value
    instance.download.return_value = 50_000_000
    instance.upload.return_value = 10_000_000
    instance.results.ping = 5.0
    instance.results.server = {"sponsor": "TestISP"}

    with patch.dict("sys.modules", {"speedtest": fake_speedtest_module}):
        first = check.run()
        second = check.run()

    assert first.details["speedtest"]["cached"] is False
    assert second.details["speedtest"]["cached"] is True
    # Speedtest itself should only have actually run once.
    assert fake_speedtest_module.Speedtest.call_count == 1
