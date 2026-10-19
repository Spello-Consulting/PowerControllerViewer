"""Configuration validation boundaries used by SCConfigManager."""

from typing import Any

import pytest
from cerberus import Validator

from config_schemas import ConfigSchema


@pytest.mark.parametrize(
    ("setting", "value", "valid"),
    [
        ("Port", 80, True),
        ("Port", 65535, True),
        ("Port", 79, False),
        ("Port", 65536, False),
        ("Port", "8000", False),
        ("PageAutoRefresh", 0, True),
        ("PageAutoRefresh", 3600, True),
        ("PageAutoRefresh", -1, False),
        ("PageAutoRefresh", 3601, False),
        ("AccessKey", None, True),
        ("AccessKey", "secret", True),
        ("AccessKey", 123, False),
        ("DebugMode", True, True),
        ("DebugMode", "true", False),
    ],
)
def test_website_validation(setting: str, value: Any, valid: bool) -> None:
    """Website settings enforce numeric bounds and supported value types."""
    assert (
        Validator(ConfigSchema().validation).validate({"Website": {setting: value}})
        is valid
    )


@pytest.mark.parametrize(
    ("setting", "value", "valid"),
    [
        ("DeleteOldStateFiles", 0, True),
        ("DeleteOldStateFiles", 168, True),
        ("DeleteOldStateFiles", -1, False),
        ("DeleteOldStateFiles", 169, False),
        ("LogfileMaxLines", 100000, True),
        ("LogfileMaxLines", 100001, False),
        ("LogfileVerbosity", "all", True),
        ("LogfileVerbosity", "invalid", False),
        ("ConsoleVerbosity", "debug", True),
        ("ConsoleVerbosity", "invalid", False),
    ],
)
def test_file_validation(setting: str, value: Any, valid: bool) -> None:
    """Retention, log size and verbosity settings reject unsupported values."""
    values = {
        "LogfileVerbosity": "summary",
        "ConsoleVerbosity": "summary",
        setting: value,
    }
    assert Validator(ConfigSchema().validation).validate({"Files": values}) is valid
