"""Shared navigation, date, runtime and currency formatting contracts."""

import datetime as dt
from typing import Any

import pytest

from view_models.common import (
    fmt_time,
    format_date_with_ordinal,
    get_currency_major,
    get_currency_minor,
    hours_to_string,
    iso_or_empty,
    nav_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "0:00"), (0, "0:00"), (1.5, "1:30"), (-2.25, "-2:15"), (24, "24:00")],
)
def test_hours(value: float | None, expected: str) -> None:
    """Durations handle missing, fractional, negative and multi-day values."""
    assert hours_to_string(value) == expected


@pytest.mark.parametrize(
    ("day", "suffix"),
    [
        (1, "st"),
        (2, "nd"),
        (3, "rd"),
        (4, "th"),
        (11, "th"),
        (12, "th"),
        (13, "th"),
        (21, "st"),
        (22, "nd"),
        (23, "rd"),
        (31, "st"),
    ],
)
def test_date_ordinals(day: int, suffix: str) -> None:
    """Ordinal suffixes include the exceptional teen dates."""
    assert format_date_with_ordinal(dt.date(2026, 10, day)) == f"{day}{suffix} October"


def test_time_and_missing_dates(fixed_clock: dt.datetime) -> None:
    """Date helpers preserve timezone information and consistent empty values."""
    assert format_date_with_ordinal(None) == "—"
    assert (
        format_date_with_ordinal(fixed_clock, show_time=True) == "19th October 12:00:00"
    )
    assert iso_or_empty(fixed_clock) == "2026-10-19T12:00:00+00:00"
    assert iso_or_empty(None) == ""  # ruff: ignore[compare-to-empty-string] - exact empty-string return contract
    assert fmt_time(None) == ""  # ruff: ignore[compare-to-empty-string] - exact empty-string return contract
    assert fmt_time(dt.time(9, 5)) == "09:05"
    assert fmt_time(fixed_clock) == "12:00"


@pytest.mark.parametrize(
    ("key", "params", "expected"),
    [
        (None, {}, "/summary"),
        ("", {"day": None}, "/summary"),
        ("secret", {"state_idx": 0, "day": None}, "/summary?state_idx=0&key=secret"),
    ],
)
def test_navigation(key: str | None, params: dict[str, Any], expected: str) -> None:
    """Navigation retains zero indexes, omits absent fields and carries access keys."""
    assert nav_url("/summary", key, **params) == expected


def test_currency_symbols() -> None:
    """Currency helpers use configured symbols and fall back when empty."""
    assert get_currency_major({}) == "$"
    assert get_currency_minor({"MinorCurrencySymbol": ""}) == "¢"
    assert get_currency_major({"MajorCurrencySymbol": "£"}) == "£"
    assert get_currency_minor({"MinorCurrencySymbol": "p"}) == "p"
