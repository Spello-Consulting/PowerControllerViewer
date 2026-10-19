"""Startup wiring, command-line options, server settings and lifespan cleanup."""

import asyncio
import runpy
import sys
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import sc_foundation

from tests.helpers import ROOT_DIR


@pytest.fixture
def main_module(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Load startup code with fake configuration and logging, avoiding credentials.

    Returns:
        The entry point namespace with mocked configuration and logging.
    """
    config = Mock()
    config.get.return_value = None
    logger = Mock()
    monkeypatch.setattr(sys, "argv", ["viewer", "--config", "test.yaml"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sc_foundation, "SCConfigManager", Mock(return_value=config))
    monkeypatch.setattr(sc_foundation, "SCLogger", Mock(return_value=logger))
    return runpy.run_path(str(ROOT_DIR / "src" / "main.py"), run_name="viewer_test")


def test_cli_defaults_override_and_invalid_arguments(
    main_module: dict[str, Any],
) -> None:
    """CLI parsing accepts the config override and rejects unknown arguments."""
    parse = main_module["parse_command_line_args"]
    assert parse([]).config == "config.yaml"
    assert (
        parse(["--config", "configs/development.yaml"]).config
        == "configs/development.yaml"
    )
    with pytest.raises(SystemExit) as error:
        parse(["--unknown"])
    assert error.value.code == 2


@pytest.mark.parametrize(
    ("settings", "host", "port", "debug"),
    [
        ({}, "127.0.0.1", 8000, False),
        (
            {"HostingIP": "192.0.2.1", "Port": "9001", "DebugMode": True},
            "192.0.2.1",
            9001,
            True,
        ),
    ],
)
def test_server_launch_settings(
    main_module: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    settings: dict[str, Any],
    host: str,
    port: int,
    debug: bool,
) -> None:
    """The entry point converts configured settings and invokes uvicorn once."""
    main_module["config"].get.side_effect = lambda _section, key: settings.get(key)
    run = Mock()
    monkeypatch.setattr(main_module["uvicorn"], "run", run)
    main_module["main"]()
    run.assert_called_once_with(
        "main:app", host=host, port=port, reload=debug, log_level="warning"
    )


def test_lifespan_loads_states_and_cancels_maintenance(
    main_module: dict[str, Any],
) -> None:
    """Startup loads existing state; shutdown cancels the background worker."""

    async def scenario() -> None:
        lifespan = main_module["lifespan"]
        globals_ = lifespan.__wrapped__.__globals__
        store = Mock(load_from_disk=AsyncMock())
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def worker(*_args: Any) -> None:
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        globals_["state_store"] = store
        globals_["housekeeping_loop"] = worker
        async with lifespan(main_module["app"]):
            store.load_from_disk.assert_awaited_once()
            await started.wait()
        await asyncio.wait_for(stopped.wait(), timeout=1)
        assert "shut down" in main_module["logger"].log_message.call_args.args[0]

    asyncio.run(scenario())


@pytest.mark.parametrize("failing_class", ["SCConfigManager", "SCLogger"])
def test_startup_errors_exit_cleanly(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failing_class: str,
) -> None:
    """Configuration and logger failures produce a readable error and exit code one."""
    monkeypatch.setattr(sys, "argv", ["viewer"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sc_foundation, "SCConfigManager", Mock(return_value=Mock()))
    monkeypatch.setattr(
        sc_foundation,
        failing_class,
        Mock(side_effect=RuntimeError("test startup failure")),
    )
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(ROOT_DIR / "src" / "main.py"), run_name="viewer_test")
    assert error.value.code == 1
    assert "test startup failure" in capsys.readouterr().err
