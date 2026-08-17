import pytest

from homedash.config import ConfigError, load_config


def test_load_config_merges_over_example_defaults(tmp_path):
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        """
home_assistant:
  base_url: "http://ha.example:8123"
  token: "abc123"
router:
  host: "10.0.0.1"
"""
    )

    config = load_config(user_config)

    # User-provided values win.
    assert config["home_assistant"]["base_url"] == "http://ha.example:8123"
    assert config["home_assistant"]["token"] == "abc123"
    assert config["router"]["host"] == "10.0.0.1"

    # Untouched keys fall back to config.example.yaml's defaults.
    assert config["refresh_interval_seconds"] == 60
    assert config["internet"]["ping_host"] == "1.1.1.1"
    assert config["home_assistant"]["verify_ssl"] is True


def test_load_config_missing_file_raises(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    with pytest.raises(ConfigError):
        load_config(missing)


def test_load_config_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("not: a: valid: mapping: [")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_load_config_non_mapping_raises(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("- just\n- a\n- list\n")
    with pytest.raises(ConfigError):
        load_config(bad)
