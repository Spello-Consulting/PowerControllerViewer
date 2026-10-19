"""Shared pytest fixtures for the PowerControllerViewer test suite."""

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from sc_foundation import DateHelper, SCCommon

from state_store import StateStore
from tests.helpers import FakeConfig, make_client, make_logger


@pytest.fixture(autouse=True)
def _clear_access_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent the shell environment from leaking an access key into tests."""
    monkeypatch.delenv("VIEWER_ACCESS_KEY", raising=False)


@pytest.fixture(autouse=True)
def isolated_state_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect state files so no test reads or modifies real device data.

    Returns:
        The temporary directory assigned to every StateStore instance.
    """
    directory = tmp_path / "state_data"
    directory.mkdir()
    original_init = StateStore.__init__

    def initialise(store: Any, logger: Any) -> None:
        original_init(store, logger)
        store.state_data_dir = directory

    monkeypatch.setattr(StateStore, "__init__", initialise)
    return directory


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> dt.datetime:
    """Freeze application dates for reproducible reporting periods and charts.

    Returns:
        The fixed aware datetime used by application date helpers.
    """
    now = dt.datetime(2026, 10, 19, 12, tzinfo=dt.UTC)
    monkeypatch.setattr(DateHelper, "now", lambda: now)
    monkeypatch.setattr(DateHelper, "today", now.date)
    monkeypatch.setattr(DateHelper, "now_str", now.isoformat)
    return now


@pytest.fixture
def config() -> Any:
    """Provide mutable application configuration.

    Returns:
        A fresh mutable configuration for each test.
    """
    return FakeConfig()


@pytest.fixture
def logger(tmp_path: Path) -> Any:
    """Provide a real logger seeded with escaped-content regression examples.

    Returns:
        A logger writing to the test temporary directory.
    """
    log = make_logger(tmp_path / "logs" / "app.log", max_lines=5)
    log.log_message("first log line", "summary")
    log.log_message("a <b>tagged</b> warning", "warning")
    return log


@pytest.fixture
def store(logger: Any) -> Any:
    """Provide the real state store in its isolated temporary directory.

    Returns:
        An empty store using the temporary state directory.
    """
    return StateStore(logger)


@pytest.fixture
def client(config: Any, logger: Any, store: Any) -> Any:
    """Provide a TestClient with real routes, templates and state persistence.

    Returns:
        An in-process client using real routes and templates.
    """
    return make_client(config, logger, store)


@pytest.fixture(autouse=True)
def isolated_host_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep system routes deterministic and avoid invoking git or sampling the host."""
    monkeypatch.setattr("routes.psutil.cpu_percent", Mock(return_value=25))
    monkeypatch.setattr(
        "routes.psutil.virtual_memory", Mock(return_value=Mock(percent=50))
    )
    monkeypatch.setattr("routes.psutil.boot_time", Mock(return_value=0))
    monkeypatch.setattr("routes.time", SimpleNamespace(time=lambda: 90060))
    monkeypatch.setattr(
        SCCommon, "get_deployment_info", Mock(return_value={"version": "test"})
    )
