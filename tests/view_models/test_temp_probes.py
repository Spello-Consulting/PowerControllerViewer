"""Probe rendering, smart-device filtering and chart time-series contracts."""

import datetime as dt
from typing import Any

import pytest

from view_models.temp_probes import build_temp_probes_view, build_temp_probes_ws_update


@pytest.mark.parametrize(
    ("temperature", "whole", "decimal", "available"),
    [(None, 0, 0, False), (0, 0, 0, True), (21.5, 21, 5, True), (-5.5, -5, -5, True)],
)
def test_probe_temperature_and_reading_fallback(
    temperature: float | None,
    whole: int,
    decimal: int,
    available: bool,
    fixed_clock: dt.datetime,
) -> None:
    """Missing, zero and negative readings retain their correct availability."""
    state = {
        "TempProbeLogging": {
            "probes": [
                {
                    "Name": "probe",
                    "DisplayName": "Room",
                    "Temperature": temperature,
                    "LastLoggedTime": fixed_clock,
                },
                {},
            ]
        }
    }
    rows = build_temp_probes_ws_update(state)["TempProbes"]
    assert rows[0] == {
        "Name": "Room",
        "HaveTemperature": available,
        "Temperature": temperature,
        "TemperatureInteger": whole,
        "TemperatureDecimal": decimal,
        "LastReadingTime": "12:00",
    }
    assert rows[1]["Name"] == "Unknown"
    assert rows[1]["LastReadingTime"] == "—"


def test_charts_filter_old_invalid_and_unselected_readings(
    fixed_clock: dt.datetime,
) -> None:
    """Chart datasets retain selected recent readings and display metadata."""
    recent = fixed_clock - dt.timedelta(days=1)
    state: dict[str, Any] = {
        "DeviceName": "Probes",
        "TempProbeLogging": {
            "probes": [{"Name": "room", "DisplayName": "Room", "Colour": "red"}],
            "history": [
                {"ProbeName": "room", "Timestamp": recent, "Temperature": 20},
                {"ProbeName": "room", "Timestamp": fixed_clock, "Temperature": 22},
                {
                    "ProbeName": "room",
                    "Timestamp": fixed_clock - dt.timedelta(days=8),
                    "Temperature": 19,
                },
                {"ProbeName": "room", "Timestamp": fixed_clock, "Temperature": None},
                {"ProbeName": "room", "Timestamp": "invalid", "Temperature": 21},
                {"ProbeName": "ignored", "Timestamp": fixed_clock, "Temperature": 21},
            ],
        },
        "Charting": {
            "Enable": True,
            "Charts": [
                {"Name": "Week", "Probes": ["room", "missing"]},
                {"Probes": ["missing"]},
            ],
        },
    }
    view = build_temp_probes_view(state, 0, None, [state], None, 0)
    assert view["ChartsEnabled"] is True
    assert len(view["ChartsData"]) == 1
    chart = view["ChartsData"][0]
    assert chart["x_min"] == int(recent.timestamp() * 1000)
    assert chart["x_max"] == int(fixed_clock.timestamp() * 1000)
    assert chart["datasets"][0] == {
        "probe_name": "room",
        "display_name": "Room",
        "colour": "red",
        "timestamps": [chart["x_min"], chart["x_max"]],
        "temperatures": [20, 22],
    }
    state["Charting"]["Enable"] = False
    assert build_temp_probes_view(state, 0, None, [], None, 0)["ChartsData"] == []


def test_summary_filters_smart_devices_and_navigation() -> None:
    """Only visible smart power outputs appear alongside temperature probes."""
    states = [
        {"StateFileType": "PowerController", "DeviceName": name, "Output": output}
        for name, output in [
            ("Visible", {"Type": "shelly", "IsOn": True}),
            ("Smart", {"Type": "smart device"}),
            ("Hidden", {"Type": "shelly", "HideFromTempProbesSummary": True}),
            ("Meter", {"Type": "meter"}),
        ]
    ]
    states.append({"StateFileType": "LightingControl"})
    view = build_temp_probes_view({}, 0, 1, states, "secret", 10, "debug")
    assert view["SmartDevices"] == [
        {"Name": "Visible", "IsOn": True},
        {"Name": "Smart", "IsOn": False},
    ]
    assert view["next_url"] == "/summary?state_idx=1&key=secret"
    assert view["ChartsEnabled"] is False
    assert view["DebugMessage"] == "debug"
