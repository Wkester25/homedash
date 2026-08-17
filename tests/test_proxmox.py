from unittest.mock import MagicMock, patch

import requests

from homedash.checks.proxmox import ProxmoxCheck
from homedash.models import Status


def make_check(**overrides):
    config = {
        "host": "pve.local",
        "port": 8006,
        "token_id": "root@pam!homedash",
        "token_secret": "secret",
        "verify_ssl": False,
        "timeout_seconds": 5,
        "nodes": [],
        "ignore_vms": [],
    }
    config.update(overrides)
    return ProxmoxCheck(config)


def _response(data):
    resp = MagicMock()
    resp.json.return_value = {"data": data}
    resp.raise_for_status = MagicMock()
    return resp


@patch("homedash.checks.proxmox.requests.get")
def test_unreachable_is_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("no route")
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR


@patch("homedash.checks.proxmox.requests.get")
def test_all_running_is_ok(mock_get):
    nodes_resp = _response([{"node": "pve1", "status": "online"}])
    qemu_resp = _response(
        [{"vmid": 100, "name": "homeassistant", "status": "running", "cpu": 0.1, "mem": 512, "maxmem": 1024, "uptime": 3600}]
    )
    lxc_resp = _response([])
    mock_get.side_effect = [nodes_resp, qemu_resp, lxc_resp]
    check = make_check()

    result = check.run()

    assert result.status == Status.OK
    assert len(result.details["vms"]) == 1


@patch("homedash.checks.proxmox.requests.get")
def test_stopped_vm_is_warn(mock_get):
    nodes_resp = _response([{"node": "pve1", "status": "online"}])
    qemu_resp = _response(
        [
            {"vmid": 100, "name": "homeassistant", "status": "running", "cpu": 0.1, "mem": 512, "maxmem": 1024, "uptime": 3600},
            {"vmid": 101, "name": "backup-vm", "status": "stopped", "cpu": 0, "mem": 0, "maxmem": 1024, "uptime": 0},
        ]
    )
    lxc_resp = _response([])
    mock_get.side_effect = [nodes_resp, qemu_resp, lxc_resp]
    check = make_check()

    result = check.run()

    assert result.status == Status.WARN
    assert "backup-vm" in result.summary


@patch("homedash.checks.proxmox.requests.get")
def test_ignored_vm_stopped_does_not_warn(mock_get):
    nodes_resp = _response([{"node": "pve1", "status": "online"}])
    qemu_resp = _response(
        [{"vmid": 101, "name": "template", "status": "stopped", "cpu": 0, "mem": 0, "maxmem": 1024, "uptime": 0}]
    )
    lxc_resp = _response([])
    mock_get.side_effect = [nodes_resp, qemu_resp, lxc_resp]
    check = make_check(ignore_vms=[101])

    result = check.run()

    assert result.status == Status.OK


@patch("homedash.checks.proxmox.requests.get")
def test_offline_node_is_error(mock_get):
    nodes_resp = _response([{"node": "pve1", "status": "offline"}])
    mock_get.side_effect = [nodes_resp]
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR
    assert "pve1" in result.summary
