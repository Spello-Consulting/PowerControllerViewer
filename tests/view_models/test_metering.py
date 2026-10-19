"""Metering date validation, period boundaries, totals and display regressions."""

import datetime as dt
from typing import Any

import pytest

from view_models.metering import (
    build_metering_reporting_data,
    build_metering_view,
    validate_metering_args,
)


@pytest.fixture
def metering_state() -> dict[str, Any]:
    """Provide global and individual usage with known totals for a custom period.

    Returns:
        Metering state with a known global total and one metered output.
    """
    return {
        "DeviceName": "Meters",
        "MajorCurrencySymbol": "£",
        "Summary": {
            "FirstDate": dt.date(2026, 9, 1),
            "LastDate": dt.date(2026, 10, 19),
        },
        "Totals": [
            {"Date": dt.date(2026, 10, 17), "EnergyUsed": 10, "Cost": 4},
            {"Date": dt.date(2026, 10, 18), "EnergyUsed": 20, "Cost": 6},
            {"Date": dt.date(2026, 9, 1), "EnergyUsed": 100, "Cost": 50},
            {"Date": "invalid"},
        ],
        "Meters": [
            {
                "DisplayName": "Pump",
                "FirstDate": dt.date(2026, 9, 1),
                "Usage": [
                    {"Date": dt.date(2026, 10, 17), "EnergyUsed": 2, "Cost": 1},
                    {"Date": dt.date(2026, 10, 18), "EnergyUsed": 4, "Cost": 1},
                    {"Date": dt.date(2026, 9, 1), "EnergyUsed": 80, "Cost": 20},
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        ({}, (None, None, None)),
        ({"period_idx": "0"}, (0, None, None)),
        ({"period_idx": "8"}, (8, None, None)),
        ({"period_idx": "-1"}, (None, None, None)),
        ({"period_idx": "9"}, (None, None, None)),
        ({"period_idx": "bad"}, (None, None, None)),
        ({"period_idx": []}, (None, None, None)),
        (
            {"start_date": "2026-09-01", "end_date": "2026-10-19", "period_idx": "0"},
            (-1, dt.date(2026, 9, 1), dt.date(2026, 10, 19)),
        ),
        (
            {"start_date": "2026-10-19", "end_date": "2026-10-19"},
            (-1, dt.date(2026, 10, 19), dt.date(2026, 10, 19)),
        ),
        ({"start_date": "2026-08-31", "end_date": "2026-10-19"}, (None, None, None)),
        ({"start_date": "2026-10-18", "end_date": "2026-10-20"}, (None, None, None)),
        ({"start_date": "2026-10-19", "end_date": "2026-10-18"}, (None, None, None)),
        (
            {"start_date": "invalid", "end_date": "2026-10-18", "period_idx": "2"},
            (2, None, None),
        ),
        ({"start_date": "2026-10-18"}, (None, None, None)),
    ],
)
def test_date_and_period_validation(
    metering_state: dict[str, Any], args: dict[str, Any], expected: tuple[Any, ...]
) -> None:
    """Custom bounds are inclusive; invalid inputs fall back to valid period choices."""
    assert validate_metering_args(metering_state, args) == expected


def test_custom_totals_percentages_and_unmetered(
    metering_state: dict[str, Any],
) -> None:
    """Custom reporting sums inclusive dates and calculates unmetered remainders."""
    start, end = dt.date(2026, 10, 17), dt.date(2026, 10, 18)
    view = build_metering_view(
        metering_state,
        0,
        1,
        [metering_state, {"DeviceName": "Next"}],
        "secret",
        10,
        -1,
        start,
        end,
    )
    total = view["Totals"][-1]
    assert total["GlobalEnergyUsed"] == 30
    assert total["GlobalCost"] == 10
    assert total["OtherEnergyUsed"] == 24
    assert total["OtherCost"] == 8
    assert total["GlobalEnergyUsedStr"] == "30.0 kWh"
    assert total["OtherEnergyUsedStr"] == "24.0 kWh (80.0%)"
    assert total["OtherCostStr"] == "£8.00 (80.0%)"
    assert view["Meters"][0]["Usage"][-1]["EnergyUsedStr"] == "6.0 kWh (20.0%)"
    assert view["Meters"][0]["Usage"][-1]["CostStr"] == "£2.00 (20.0%)"
    assert view["ShowUnmetered"] is True
    assert view["PeriodChoiceList"][-1]["Selected"] is True
    assert view["CustomStartDate"] == "2026-10-17"
    assert view["next_url"] == "/summary?state_idx=1&key=secret"


def test_no_global_totals_aggregate_meters(metering_state: dict[str, Any]) -> None:
    """Controllers without global data report meter sums and hide unmetered rows."""
    metering_state["Totals"] = []
    view = build_metering_view(
        metering_state,
        0,
        None,
        [],
        None,
        0,
        -1,
        dt.date(2026, 10, 17),
        dt.date(2026, 10, 18),
    )
    total = view["Totals"][-1]
    assert total["HaveData"] is True
    assert total["GlobalEnergyUsed"] == 6
    assert total["GlobalCost"] == 2
    assert total["OtherEnergyUsedStr"] == "N/A"
    assert total["OtherCostStr"] == "N/A"
    assert view["ShowUnmetered"] is False
    assert view["Meters"][0]["Usage"][-1]["EnergyUsedStr"] == "6.0 kWh"


def test_reporting_calendar_boundaries(metering_state: dict[str, Any]) -> None:
    """Monday and month-start period bounds never produce reversed ranges."""
    data = build_metering_reporting_data(metering_state, None, None, None)
    periods = {p.name: p for p in data["ReportingPeriods"]}
    assert (
        periods["This Week"].start_date
        == periods["This Week"].end_date
        == dt.date(2026, 10, 19)
    )
    assert periods["Last Week"].start_date == dt.date(2026, 10, 12)
    assert periods["Last Week"].end_date == dt.date(2026, 10, 18)
    assert periods["Last Month"].start_date == dt.date(2026, 9, 1)
    assert periods["Last Month"].end_date == dt.date(2026, 9, 30)
    assert periods["Last 30 Days"].start_date == dt.date(2026, 9, 19)


def test_month_start_bounds(
    metering_state: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first day of January handles year and month boundaries."""
    monkeypatch.setattr(
        "view_models.metering.DateHelper.today", lambda: dt.date(2026, 1, 1)
    )
    periods = {
        p.name: p
        for p in build_metering_reporting_data(metering_state, None, None, None)[
            "ReportingPeriods"
        ]
    }
    assert (
        periods["This Month"].start_date
        == periods["This Month"].end_date
        == dt.date(2026, 1, 1)
    )
    assert periods["Last Month"].start_date == dt.date(2025, 12, 1)


def test_late_meters_and_small_readings(metering_state: dict[str, Any]) -> None:
    """Incomplete meter coverage shows N/A; zero or tiny usage shows a dash."""
    metering_state["Totals"] = []
    metering_state["Meters"] = [
        {"Output": "Late", "FirstDate": dt.date(2026, 10, 18)},
        {"Usage": [{"Date": dt.date(2026, 10, 18), "EnergyUsed": 0.05, "Cost": None}]},
    ]
    view = build_metering_view(
        metering_state,
        0,
        None,
        [],
        None,
        0,
        -1,
        dt.date(2026, 10, 17),
        dt.date(2026, 10, 18),
    )
    assert view["Meters"][0]["Name"] == "Late"
    assert view["Meters"][0]["Usage"][-1]["EnergyUsedStr"] == "N/A"
    assert view["Meters"][1]["Name"] == "Unknown"
    assert view["Meters"][1]["Usage"][-1]["EnergyUsedStr"] == "-"
    assert view["Meters"][1]["Usage"][-1]["CostStr"] == "-"


def test_no_data_totals_and_period_menu(metering_state: dict[str, Any]) -> None:
    """No readings produce N/A totals and the menu omits automatic periods."""
    metering_state.update(Totals=[], Meters=[])
    view = build_metering_view(metering_state, 0, None, [], None, 0, 0)
    assert all(
        t["GlobalCostStr"] == t["GlobalEnergyUsedStr"] == "N/A" for t in view["Totals"]
    )
    assert view["PeriodChoiceList"][0]["Selected"] is True
    assert not view["PeriodChoiceList"][-1]["Selected"]
    assert "Yesterday" not in [p["Name"] for p in view["PeriodChoiceList"]]
