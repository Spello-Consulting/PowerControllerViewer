"""WebSocket connection lifecycle, dead-client isolation and JSON encoding."""

import asyncio
import datetime as dt
import json
from unittest.mock import AsyncMock

from fastapi.websockets import WebSocketState

from websocket_manager import ConnectionManager, _ws_dumps  # ruff: ignore[import-private-name] - shared wire serializer contract


def test_json_encoding_preserves_temporal_values(fixed_clock: dt.datetime) -> None:
    """Wire JSON encodes datetime, date, time and fallback objects predictably."""
    result = json.loads(
        _ws_dumps(
            {
                "datetime": fixed_clock,
                "date": fixed_clock.date(),
                "time": dt.time(9, 5, 3),
                "other": complex(1, 2),
            }
        )
    )
    assert result == {
        "datetime": fixed_clock.isoformat(),
        "date": "2026-10-19",
        "time": "09:05:03",
        "other": "(1+2j)",
    }


def test_broadcast_isolates_and_removes_dead_connections() -> None:
    """One failed client cannot block broadcasts or survive into later sends."""

    async def scenario() -> None:
        manager = ConnectionManager()
        healthy = AsyncMock(client_state=WebSocketState.CONNECTED)
        dead = AsyncMock(client_state=WebSocketState.CONNECTED)
        inactive = AsyncMock(client_state=WebSocketState.DISCONNECTED)
        dead.send_json.side_effect = RuntimeError("closed")
        for ws in [healthy, dead, inactive]:
            await manager.connect(ws)
            ws.accept.assert_awaited_once()
        await manager.broadcast({"message": 1})
        await manager.broadcast({"message": 2})
        assert healthy.send_json.await_count == 2
        assert dead.send_json.await_count == 1
        inactive.send_json.assert_not_awaited()
        manager.disconnect(healthy)
        manager.disconnect(healthy)
        await manager.broadcast({})
        assert healthy.send_json.await_count == 2

    asyncio.run(scenario())


def test_direct_send_failure_removes_connection() -> None:
    """A direct-send failure drops the failed socket from subsequent broadcasts."""

    async def scenario() -> None:
        manager = ConnectionManager()
        ws = AsyncMock(client_state=WebSocketState.CONNECTED)
        await manager.connect(ws)
        await manager.send(ws, {"ok": True})
        ws.send_json.assert_awaited_once_with({"ok": True})
        ws.send_json.side_effect = RuntimeError("closed")
        await manager.send(ws, {})
        await manager.broadcast({})
        assert ws.send_json.await_count == 2

    asyncio.run(scenario())
