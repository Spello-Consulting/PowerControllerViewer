"""State persistence, disk reconciliation, retention and subscriber regression tests."""

import asyncio
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from sc_foundation import SCCommon

from state_store import StateStore
from tests.helpers import STATE_TYPES, state_payload


def write_state(directory: Path, name: str = "Test Device", **changes: Any) -> Path:
    """Write a producer payload as a standalone external state file.

    Returns:
        The path of the written state file.
    """
    path = directory / f"{name}.json"
    path.write_text(
        json.dumps(dict(state_payload(name=name), **changes)), encoding="utf-8"
    )
    return path


@pytest.mark.parametrize("state_type", STATE_TYPES)
def test_load_decodes_and_enriches(store: Any, state_type: str) -> None:
    """Startup loads wire dates into aware datetimes and supplies device metadata."""
    payload = state_payload(state_type)
    (store.state_data_dir / "device.json").write_text(json.dumps(payload))
    asyncio.run(store.load_from_disk())
    state = store.get_by_device_name("Test Device")
    assert isinstance(state["LocalLastSaveTime"], dt.datetime)
    assert state["LocalLastSaveTime"].utcoffset() is not None
    assert state["StateURLName"] == "TestDevice"
    assert state["_file_mtime"] > 0


def test_load_skips_invalid_and_unrelated_files(store: Any) -> None:
    """One corrupt file cannot prevent valid devices loading on startup."""
    for name, text in [
        ("bad.json", "{"),
        ("empty.json", ""),
        ("list.json", "[]"),
        (".hidden.json", "{}"),
        ("notes.txt", "{}"),
    ]:
        (store.state_data_dir / name).write_text(text)
    (store.state_data_dir / "folder.json").mkdir()
    write_state(store.state_data_dir)
    asyncio.run(store.load_from_disk())
    assert store.count() == 1


def test_missing_directory_is_harmless(store: Any, tmp_path: Path) -> None:
    """An absent startup directory and external scan do not fail."""
    store.state_data_dir = tmp_path / "missing"
    asyncio.run(store.load_from_disk())
    asyncio.run(store.check_external_changes())
    assert store.count() == 0


@pytest.mark.parametrize(
    ("state_type", "output_type", "description"),
    [
        ("PowerController", "teslamate", "Tesla Charging"),
        ("PowerController", "meter", "Energy Meter"),
        ("PowerController", "shelly", "Power Controller"),
        ("LightingControl", "", "Lighting Controller"),
        ("TempProbes", "", "Temperature Probes"),
        ("OutputMetering", "", "Metered Outputs"),
        ("Other", "", "Unknown Device"),
    ],
)
def test_enrichment_descriptions_and_names(
    state_type: str, output_type: str, description: str, fixed_clock: dt.datetime
) -> None:
    """Device type descriptions, fallback times and URL names are stable."""
    state = StateStore._enrich(  # ruff: ignore[private-member-access] - verify producer metadata
        {
            "StateFileType": state_type,
            "DeviceName": "A /B\\-é",
            "Output": {"Type": output_type},
        }
    )
    assert state["DeviceDescription"] == description
    assert state["StateURLName"] == "AB%C3%A9"
    assert state["LocalLastSaveTime"] == fixed_clock.astimezone()


def test_read_apis_sort_lookup_and_bounds(store: Any) -> None:
    """Indexes always follow device-name ordering and invalid lookups return None."""

    async def scenario() -> None:
        await store.save_and_update(state_payload(name="Zulu"))
        await store.save_and_update(state_payload(name="Alpha"))

    asyncio.run(scenario())
    assert [s["DeviceName"] for s in store.get_all_states()] == ["Alpha", "Zulu"]
    assert store.get_by_index(0)["DeviceName"] == "Alpha"
    assert store.get_index_by_url_name("Zulu") == 1
    assert store.get_index_by_url_name("missing") is None
    assert store.get_by_device_name("missing") is None
    assert store.get_by_index(-1) is None
    assert store.get_by_index(2) is None


def test_save_notifies_all_subscribers_and_unsubscribe_is_idempotent(
    store: Any,
) -> None:
    """Subscribers receive device updates, and unsubscribed queues receive none."""

    async def scenario() -> None:
        first, second = store.subscribe(), store.subscribe()
        await store.save_and_update(state_payload())
        assert first.get_nowait() == second.get_nowait() == "Test Device"
        store.unsubscribe(first)
        store.unsubscribe(first)
        await store.save_and_update(state_payload())
        assert first.empty()
        assert second.get_nowait() == "Test Device"
        assert not (store.state_data_dir / "Test Device.tmp").exists()

    asyncio.run(scenario())


def test_external_add_modify_delete_and_unchanged_file(store: Any) -> None:
    """External disk changes update canonical devices and publish deletion events."""

    async def scenario() -> None:
        queue = store.subscribe()
        path = write_state(store.state_data_dir)
        await store.check_external_changes()
        assert queue.get_nowait() == "Test Device"
        await store.check_external_changes()
        assert queue.empty()
        write_state(store.state_data_dir, Output={"IsOn": False})
        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 10))
        await store.check_external_changes()
        assert queue.get_nowait() == "Test Device"
        assert store.get_by_device_name("Test Device")["Output"]["IsOn"] is False
        path.unlink()
        await store.check_external_changes()
        assert queue.get_nowait() == "__deleted__:Test Device"
        assert store.count() == 0

    asyncio.run(scenario())


def test_external_filename_can_differ_from_device_name(store: Any) -> None:
    """A canonical name differing from its filename survives repeated scans."""

    async def scenario() -> None:
        queue = store.subscribe()
        write_state(store.state_data_dir, "external", DeviceName="Canonical")
        await store.check_external_changes()
        assert queue.get_nowait() == "Canonical"
        await store.check_external_changes()
        assert queue.empty()
        assert store.get_by_device_name("Canonical") is not None

    asyncio.run(scenario())


def test_external_corrupt_file_keeps_last_good_state(store: Any) -> None:
    """A partial external write retains the previously loaded device state."""

    async def scenario() -> None:
        path = write_state(store.state_data_dir)
        await store.load_from_disk()
        path.write_text("{")
        os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 10))
        await store.check_external_changes()
        assert store.count() == 1

    asyncio.run(scenario())


def test_retention_removes_only_expired_files(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retention preserves recent files and removes expired in-memory entries."""
    old = write_state(store.state_data_dir, "Old")
    recent = write_state(store.state_data_dir, "Recent")
    os.utime(old, (1000, 1000))
    os.utime(recent, (10000, 10000))
    asyncio.run(store.load_from_disk())
    monkeypatch.setattr("state_store.time.time", lambda: 10000)
    store.delete_old_files(1)
    assert not old.exists()
    assert recent.exists()
    assert [s["DeviceName"] for s in store.get_all_states()] == ["Recent"]


def test_retention_logs_unlink_error(
    store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem deletion error preserves the device for later retries."""
    path = write_state(store.state_data_dir)
    os.utime(path, (1, 1))
    asyncio.run(store.load_from_disk())
    monkeypatch.setattr(Path, "unlink", Mock(side_effect=PermissionError("denied")))
    store.delete_old_files(1)
    assert store.count() == 1


def test_directory_resolution_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """State storage falls back to a relative directory if discovery fails."""
    monkeypatch.setattr(SCCommon, "select_file_location", lambda _name: None)
    assert StateStore._resolve_state_dir() == Path("state_data")  # ruff: ignore[private-member-access] - regression coverage of internal lifecycle contracts
