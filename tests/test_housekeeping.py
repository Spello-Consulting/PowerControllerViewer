"""Periodic maintenance, reload behaviour, failure isolation and cancellation."""

import asyncio
import datetime as dt
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from housekeeping import housekeeping_loop


@pytest.mark.parametrize("reload_config", [False, True])
@pytest.mark.parametrize("max_age", [None, 0, -1, "24", 2.5])
def test_maintenance_cycle(
    monkeypatch: pytest.MonkeyPatch, reload_config: bool, max_age: Any
) -> None:
    """A cycle trims logs, reloads settings, expires files and checks external changes."""

    async def scenario() -> None:
        config = Mock()
        config.check_for_config_changes.return_value = reload_config
        config.get.return_value = max_age
        config.get_email_settings.return_value = {"server": "example"}
        logger = Mock()
        store = Mock(check_external_changes=AsyncMock())
        sleep = AsyncMock(side_effect=[None, asyncio.CancelledError])
        monkeypatch.setattr("housekeeping.asyncio.sleep", sleep)
        with pytest.raises(asyncio.CancelledError):
            await housekeeping_loop(config, logger, store)
        logger.trim_logfile.assert_called_once_with()
        logger.ping_heartbeat.assert_called_once_with()
        store.check_external_changes.assert_awaited_once_with()
        if isinstance(max_age, float):
            store.delete_old_files.assert_called_once_with(2)
        else:
            store.delete_old_files.assert_not_called()
        if reload_config:
            logger.initialise_settings.assert_called_once_with(
                config.get_logger_settings.return_value
            )
            logger.register_email_settings.assert_called_once_with(
                {"server": "example"}
            )
        else:
            logger.initialise_settings.assert_not_called()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure", ["config", "trim", "delete", "external", "heartbeat"]
)
def test_maintenance_failures_do_not_stop_loop(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Independent maintenance failures are logged or suppressed and the loop continues."""

    async def scenario() -> None:
        config = Mock()
        config.get.return_value = 24
        config.check_for_config_changes.return_value = False
        logger = Mock()
        store = Mock(check_external_changes=AsyncMock())
        target = {
            "config": config.check_for_config_changes,
            "trim": logger.trim_logfile,
            "delete": store.delete_old_files,
            "external": store.check_external_changes,
            "heartbeat": logger.ping_heartbeat,
        }[failure]
        target.side_effect = RuntimeError("test failure")
        monkeypatch.setattr(
            "housekeeping.asyncio.sleep",
            AsyncMock(side_effect=[None, asyncio.CancelledError]),
        )
        with pytest.raises(asyncio.CancelledError):
            await housekeeping_loop(config, logger, store)
        logger.ping_heartbeat.assert_called_once()
        if failure in {"config", "delete", "external"}:
            assert "test failure" in logger.log_message.call_args.args[0]

    asyncio.run(scenario())


def test_reload_timestamp_advances_and_absent_email_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The next reload check uses the successful reload time and tolerates no email."""

    async def scenario() -> None:
        config = Mock()
        config.check_for_config_changes.return_value = True
        first = dt.datetime(2026, 10, 19, 12, tzinfo=dt.UTC)
        second = first + dt.timedelta(seconds=10)
        third = second + dt.timedelta(seconds=10)
        monkeypatch.setattr(
            "housekeeping.DateHelper.now", Mock(side_effect=[first, second, third])
        )
        config.get.return_value = 0
        config.get_email_settings.return_value = None
        logger = Mock()
        store = Mock(check_external_changes=AsyncMock())
        monkeypatch.setattr(
            "housekeeping.asyncio.sleep",
            AsyncMock(side_effect=[None, None, asyncio.CancelledError]),
        )
        with pytest.raises(asyncio.CancelledError):
            await housekeeping_loop(config, logger, store)
        assert [
            call.args[0] for call in config.check_for_config_changes.call_args_list
        ] == [first, second]
        logger.register_email_settings.assert_not_called()

    asyncio.run(scenario())


def test_cancellation_during_maintenance_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shutdown cancellation is never swallowed by maintenance error handling."""

    async def scenario() -> None:
        config = Mock()
        config.check_for_config_changes.return_value = False
        config.get.return_value = 0
        store = Mock(
            check_external_changes=AsyncMock(side_effect=asyncio.CancelledError)
        )
        monkeypatch.setattr("housekeeping.asyncio.sleep", AsyncMock(return_value=None))
        with pytest.raises(asyncio.CancelledError):
            await housekeeping_loop(config, Mock(), store)

    asyncio.run(scenario())
