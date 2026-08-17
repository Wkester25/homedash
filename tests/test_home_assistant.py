from unittest.mock import MagicMock, patch

import requests

from homedash.checks.home_assistant import HomeAssistantCheck
from homedash.models import Status


def make_check(**overrides):
    config = {
        "base_url": "http://ha.local:8123",
        "token": "sekret",
        "verify_ssl": True,
        "timeout_seconds": 5,
        "check_entities": True,
        "ignore_entities": [],
    }
    config.update(overrides)
    return HomeAssistantCheck(config)


def _response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    return resp


@patch("homedash.checks.home_assistant.requests.get")
def test_unreachable_is_error(mock_get):
    mock_get.side_effect = requests.ConnectionError("refused")
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR
    assert "unreachable" in result.summary.lower()


@patch("homedash.checks.home_assistant.requests.get")
def test_bad_token_is_error(mock_get):
    mock_get.return_value = _response(status_code=401)
    check = make_check()

    result = check.run()

    assert result.status == Status.ERROR
    assert "unauthorized" in result.summary.lower()


@patch("homedash.checks.home_assistant.requests.get")
def test_all_entities_available_is_ok(mock_get):
    api_resp = _response(json_data={"message": "API running."})
    states_resp = _response(
        json_data=[
            {"entity_id": "light.kitchen", "state": "on"},
            {"entity_id": "sensor.temp", "state": "72"},
        ]
    )
    mock_get.side_effect = [api_resp, states_resp]
    check = make_check()

    result = check.run()

    assert result.status == Status.OK
    assert result.details["unavailable_entities"] == []


@patch("homedash.checks.home_assistant.requests.get")
def test_unavailable_entities_trigger_warn(mock_get):
    api_resp = _response(json_data={"message": "API running."})
    states_resp = _response(
        json_data=[
            {"entity_id": "light.kitchen", "state": "unavailable"},
            {"entity_id": "sensor.temp", "state": "72"},
            {"entity_id": "lock.front_door", "state": "unknown"},
        ]
    )
    mock_get.side_effect = [api_resp, states_resp]
    check = make_check()

    result = check.run()

    assert result.status == Status.WARN
    assert len(result.details["unavailable_entities"]) == 2


@patch("homedash.checks.home_assistant.requests.get")
def test_ignored_entities_are_excluded(mock_get):
    api_resp = _response(json_data={"message": "API running."})
    states_resp = _response(
        json_data=[
            {"entity_id": "device_tracker.phone", "state": "unavailable"},
        ]
    )
    mock_get.side_effect = [api_resp, states_resp]
    check = make_check(ignore_entities=["device_tracker.phone"])

    result = check.run()

    assert result.status == Status.OK
