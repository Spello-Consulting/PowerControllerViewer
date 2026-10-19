"""Device grouping, status text and home WebSocket payloads."""

import datetime as dt
from typing import Any

import pytest

from view_models.home import build_home_device_ws, build_home_view


@pytest.mark.parametrize(
    ("state", "running", "status"),
    [
        (
            {
                "StateFileType": "LightingControl",
                "SwitchStates": [{"OutputState": "ON"}],
            },
            True,
            "1 light on",
        ),
        (
            {
                "StateFileType": "LightingControl",
                "SwitchStates": [{"OutputState": "ON"}, {"OutputState": "ON"}],
            },
            True,
            "2 lights on",
        ),
        ({"StateFileType": "LightingControl"}, False, "0 lights on"),
        ({"StateFileType": "PowerController", "Output": {"IsOn": True}}, True, "On."),
        ({"StateFileType": "PowerController", "Output": {}}, False, "Off."),
        (
            {
                "StateFileType": "PowerController",
                "Output": {
                    "Type": "shelly",
                    "IsOn": True,
                    "RunPlan": {"RemainingHours": 1.5},
                },
            },
            True,
            "On, 1:30 remaining today.",
        ),
        (
            {"StateFileType": "PowerController", "Output": {"Type": "smart device"}},
            False,
            "Not running, 0:00 remaining today.",
        ),
        (
            {"StateFileType": "TempProbes", "TempProbeLogging": {"probes": [{}]}},
            False,
            "1 probe active.",
        ),
        ({"StateFileType": "TempProbes"}, False, "0 probes active."),
        ({"StateFileType": "OutputMetering", "Meters": [{}]}, False, "1 meter logged."),
        (
            {"StateFileType": "OutputMetering", "Meters": [{}, {}]},
            False,
            "2 meters logged.",
        ),
        ({"StateFileType": "Unknown"}, False, ""),
    ],
)
def test_device_status(state: dict[str, Any], running: bool, status: str) -> None:
    """Home live updates describe each producer's actual running state."""
    row = build_home_device_ws(state)
    assert row["is_running"] is running
    assert row["status"] == status


@pytest.mark.parametrize("output_type", ["shelly", "meter"])
def test_running_status_includes_start(
    output_type: str, fixed_clock: dt.datetime
) -> None:
    """Known start times appear in running device status text."""
    row = build_home_device_ws(
        {
            "StateFileType": "PowerController",
            "Output": {
                "Type": output_type,
                "IsOn": True,
                "RunHistory": {"LastStartTime": fixed_clock},
            },
        }
    )
    assert row["status"].startswith("On at 12:00")


def test_groups_latest_timestamp_and_navigation(fixed_clock: dt.datetime) -> None:
    """Groups follow the producer display order and use the newest valid save."""
    states = [
        {
            "StateFileType": kind,
            "DeviceName": kind,
            "_idx": i,
            "LocalLastSaveTime": fixed_clock - dt.timedelta(hours=i),
        }
        for i, kind in enumerate(
            [
                "Other",
                "OutputMetering",
                "TempProbes",
                "LightingControl",
                "PowerController",
            ]
        )
    ]
    view = build_home_view(states, "secret", 15)
    assert view["TotalDevices"] == 5
    assert [g["StateFileType"] for g in view["DeviceGroups"]] == [
        "PowerController",
        "LightingControl",
        "TempProbes",
        "OutputMetering",
        "Other",
    ]
    assert view["LastCheckISO"] == fixed_clock.isoformat()
    assert view["RefreshDelay"] == 15
    assert (
        view["DeviceGroups"][0]["Devices"][0]["summary_url"]
        == "/summary?state_idx=4&key=secret"
    )
    assert build_home_view([], None, 0)["LastCheck"] == "—"
    assert build_home_view([{}], None, 0)["LastCheckISO"] == ""  # ruff: ignore[compare-to-empty-string] - exact empty-string return contract
