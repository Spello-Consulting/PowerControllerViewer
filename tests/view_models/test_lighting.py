"""Lighting schedules, physical triggers, daily events and WebSocket updates."""

import datetime as dt
from typing import Any

from view_models.lighting import (
    build_lighting_daily_view,
    build_lighting_view,
    build_lighting_ws_update,
)


def test_schedule_triggers_are_separated_without_mutating_state(
    fixed_clock: dt.datetime,
) -> None:
    """Known schedules are promoted, while physical and explicit triggers survive."""
    switches = [
        {"Switch": "A", "Input": "Evening", "OutputState": "ON"},
        {"Switch": "B", "Input": "Button"},
        {"Switch": "C", "Input": "Evening", "Schedule": "Explicit"},
    ]
    state: dict[str, Any] = {
        "DeviceName": "Lights",
        "SwitchStates": switches,
        "Dawn": fixed_clock,
        "Dusk": fixed_clock,
        "Schedules": [
            {
                "Name": "Evening",
                "Events": [
                    {
                        "DaysOfWeek": "Mon, Wed",
                        "DatesOff": [
                            {"StartDate": dt.date(2026, 10, 1), "EndDate": None}
                        ],
                    },
                    {"DaysOfWeek": "All"},
                    {},
                ],
            }
        ],
        "SwitchEvents": [{}],
    }
    view = build_lighting_view(
        state, 0, 1, [state, {"DeviceName": "Next"}], "secret", 10
    )
    assert view["SwitchStates"][0]["Schedule"] == "Evening"
    assert view["SwitchStates"][0]["Input"] is None
    assert view["SwitchStates"][1]["Input"] == "Button"
    assert view["SwitchStates"][2]["Schedule"] == "Explicit"
    assert switches[0]["Input"] == "Evening"
    assert "Schedule" not in switches[0]
    events = view["Schedules"][0]["Events"]
    assert [d["Day"] for d in events[0]["DaysEnabled"] if d["Enabled"]] == [
        "Mon",
        "Wed",
    ]
    assert all(d["Enabled"] for d in events[1]["DaysEnabled"])
    assert not any(d["Enabled"] for d in events[2]["DaysEnabled"])
    assert events[0]["DatesOff"][0]["StartDateAU"] == "1 Oct 26"
    assert events[0]["DatesOff"][0]["EndDateAU"] == ""  # ruff: ignore[compare-to-empty-string] - exact empty-string return contract
    assert view["DawnTime"] == view["DuskTime"] == "12:00"
    assert view["daily_url"] == "/daily?state_idx=0&key=secret"
    assert view["NextDeviceName"] == "Next"


def test_daily_events_sort_dates_and_choose_trigger() -> None:
    """Newest events appear first, with schedule, input and fallback triggers."""
    state = {
        "SwitchEvents": [
            {"Date": dt.date(2026, 10, 17)},
            {
                "Date": dt.date(2026, 10, 18),
                "Events": [
                    {
                        "Time": dt.time(18, 30),
                        "Switch": "A",
                        "Schedule": "Dusk",
                        "Input": "Button",
                        "State": "ON",
                    },
                    {"Input": "Button"},
                    {},
                ],
            },
        ]
    }
    view = build_lighting_daily_view(state, 0, 0, 1, None, 0)
    assert view["Date"] == "18/10/2026"
    assert [e["Trigger"] for e in view["Events"]] == ["Dusk", "Button", "No Trigger"]
    assert view["Events"][0]["Time"] == "18:30"
    assert view["Events"][2] == {
        "Time": "?",
        "Switch": "Unknown",
        "Trigger": "No Trigger",
        "State": "OFF",
    }
    assert view["PreviousDay"] == 1
    assert view["NextDay"] is None
    assert build_lighting_daily_view(state, 0, 1, 1, None, 0)["NextDay"] == 0
    assert build_lighting_daily_view({}, 0, 0, 0, None, 0)["Date"] == "Unknown"


def test_lighting_defaults_and_serialisable_live_fields() -> None:
    """Missing data is safe and live switch fields exclude raw time objects."""
    view = build_lighting_view({}, 0, None, [], None, 0)
    assert view["daily_url"] is None
    assert view["HaveSwitchStates"] is False
    assert view["DawnTime"] is None
    update = build_lighting_ws_update(
        {
            "SwitchStates": [
                {
                    "Switch": "A",
                    "OutputState": "ON",
                    "InputState": "OFF",
                    "Time": dt.time(1),
                }
            ]
        }
    )
    assert update["SwitchStates"] == [
        {"Switch": "A", "OutputState": "ON", "InputState": "OFF"}
    ]
