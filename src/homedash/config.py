"""Loads and validates config.yaml (see config.example.yaml for the schema)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"
EXAMPLE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.example.yaml"


class ConfigError(RuntimeError):
    """Raised when config.yaml is missing or malformed."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge `override` onto `base`, recursing into nested dicts.

    Used so a user's config.yaml only needs to set the keys they care about;
    anything omitted falls back to the shipped example's defaults.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load config.yaml, layered on top of config.example.yaml's defaults.

    Raises ConfigError if the requested file doesn't exist or isn't valid
    YAML/a mapping at the top level.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH

    defaults: dict[str, Any] = {}
    if EXAMPLE_CONFIG_PATH.exists():
        defaults = yaml.safe_load(EXAMPLE_CONFIG_PATH.read_text()) or {}

    if not config_path.exists():
        if path is not None:
            # User explicitly pointed at a file that doesn't exist.
            raise ConfigError(f"Config file not found: {config_path}")
        raise ConfigError(
            f"No config.yaml found at {config_path}. "
            f"Copy config.example.yaml to config.yaml and fill in your details."
        )

    try:
        user_config = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse {config_path}: {exc}") from exc

    if not isinstance(user_config, dict):
        raise ConfigError(f"{config_path} must contain a YAML mapping at the top level")

    return _deep_merge(defaults, user_config)
