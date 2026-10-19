"""Power runtime, pricing, daily history and live-update calculations."""

import datetime as dt
from typing import Any

import pytest

from view_models.power import (
    build_power_daily_view,
    build_power_view,
    build_power_ws_update,
)


@pytest.fixture
def power_state(fixed_clock: dt.datetime) -> dict[str, Any]:
    """Provide realistic runtime, price and run-plan data.

    Returns:
        Power state containing a run plan and daily history.
    """
    return {
        "DeviceName": "Canonical",
        "LocalLastSaveTime": fixed_clock,
        "MajorCurrencySymbol": "£",
        "MinorCurrencySymbol": "p",
        "Output": {
            "Name": "Pool Pump",
            "IsOn": True,
            "DeviceMode": "BestPrice",
            "Reason": "Cheap power",
            "RunPlan": {
                "RemainingHours": 1.5,
                "ForecastAveragePrice": 12.25,
                "RunPlan": [
                    {
                        "StartDateTime": fixed_clock,
                        "EndDateTime": fixed_clock + dt.timedelta(hours=1.5),
                        "Minutes": 90,
                        "Price": 12.25,
                    },
                    {},
                ],
            },
            "RunHistory": {
                "LastStartTime": fixed_clock,
                "CurrentPrice": 15,
                "AlltimeTotals": {"HourlyEnergyUsed": 1000, "AveragePrice": 20},
                "CurrentTotals": {"ActualHoursPerDay": 2.5},
                "DailyData": [
                    {
                        "Date": dt.date(2026, 10, 18),
                        "TargetHours": 4,
                        "PriorShortfall": 0.5,
                        "ActualHours": 2,
                        "EnergyUsed": 2500,
                        "AveragePrice": 20,
                        "TotalCost": 0.5,
                        "DeviceRuns": [
                            {
                                "StartTime": fixed_clock,
                                "ActualHours": 2,
                                "AveragePrice": None,
                            }
                        ],
                    }
                ],
            },
        },
    }


def test_summary_calculates_runtime_energy_cost_and_navigation(
    power_state: dict[str, Any],
) -> None:
    """Summary converts units and preserves canonical names for live updates."""
    view = build_power_view(
        power_state, 0, 1, [power_state, {"DeviceName": "Next"}], "secret", 10, "debug"
    )
    assert view["DeviceName"] == "Pool Pump"
    assert view["PageDevice"] == "Canonical"
    assert view["PlannedRuntime"] == "2:30"
    assert view["TargetRuntime"] == "4:00"
    assert view["AverageDailyUsage"] == 24
    assert view["AverageDailyCost"] == "£4.80"
    assert view["PumpStatus"] == "Started at 12:00:00"
    assert view["LivePrices"] is True
    assert view["RunPlan"] == [
        {
            "From": "12:00",
            "To": "13:30",
            "Duration": "1:30",
            "AveragePrice": "12.2 p/kWh",
        }
    ]
    assert view["next_url"] == "/summary?state_idx=1&key=secret"
    assert view["DebugMessage"] == "debug"


@pytest.mark.parametrize("target", [-1, None])
def test_unplanned_runtime_and_empty_defaults(target: int | None) -> None:
    """Sentinel and absent targets hide planned runtime instead of going negative."""
    state = {"Output": {"RunHistory": {"DailyData": [{"TargetHours": target}]}}}
    view = build_power_view(state, 0, None, [state], None, 0)
    assert view["ShowPlannedRuntime"] is False
    assert view["PumpStatus"] == "Not running"
    assert view["next_url"] is None
    assert view["HaveRunPlan"] is False
    assert build_power_view({}, 0, None, [], None, 0)["DeviceName"] == "Unknown"


def test_daily_history_is_newest_first_and_formats_runs(
    power_state: dict[str, Any],
) -> None:
    """Daily navigation sorts history and handles an ongoing run."""
    older = dict(
        power_state["Output"]["RunHistory"]["DailyData"][0], Date=dt.date(2026, 10, 17)
    )
    power_state["Output"]["RunHistory"]["DailyData"].append(older)
    view = build_power_daily_view(power_state, 2, 0, 1, "secret", 0)
    assert view["Date"] == "18/10/2026"
    assert view["ActualRuntime"] == "2:00 hrs run, 2:30 hrs remaining"
    assert view["EnergyUsed"] == "2.50 kWh at 20.0 p/kWh = £0.50"
    assert view["DeviceRuns"][0] == {
        "Start": "12:00",
        "End": "Running",
        "Duration": "2:00",
        "Price": "?",
    }
    assert view["prev_day_url"] == "/daily?state_idx=2&day=1&key=secret"
    assert view["next_day_url"] is None
    last = build_power_daily_view(power_state, 2, 1, 1, None, 0)
    assert last["prev_day_url"] is None
    assert last["next_day_url"] == "/daily?state_idx=2&day=0"


def test_empty_daily_and_live_update(power_state: dict[str, Any]) -> None:
    """Empty history remains renderable and live fields agree with the summary."""
    empty = build_power_daily_view({}, 0, 0, 0, None, 0)
    assert empty["Date"] == "Unknown"
    assert empty["HaveRunPlan"] is False
    update = build_power_ws_update(power_state)
    assert update["ActualRuntime"] == "2:00"
    assert update["RemainingRuntime"] == "1:30"
    assert update["CurrentPrice"] == "15 p/kWh"
    assert update["StatusMessage"] == "Cheap power"
    assert (
        build_power_ws_update({"Output": {"IsOn": True}})["PumpStatus"]
        == "Started at Unknown"
    )
