"""Real ASGI WebSocket authentication, snapshots, updates and subscription cleanup."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.helpers import STATE_TYPES, state_payload


@pytest.mark.parametrize("key", [None, "wrong"])
def test_websocket_rejects_invalid_key(
    client: TestClient, config: Any, key: str | None
) -> None:
    """Unauthorised socket connections close with the policy-violation code."""
    config.set("Website", "AccessKey", "secret")
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect("/ws" + (f"?key={key}" if key else "")),
    ):
        pytest.fail("Unauthorised websocket was accepted")
    assert error.value.code == 1008


@pytest.mark.parametrize("state_type", STATE_TYPES)
def test_websocket_initial_and_live_updates(
    client: TestClient, config: Any, state_type: str
) -> None:
    """A submission updates an authenticated socket with the correct producer fields."""
    config.set("Website", "AccessKey", "secret")
    with client, client.websocket_connect("/ws?key=secret") as socket:
        assert socket.receive_json() == {"type": "initial", "devices": []}
        response = client.post("/api/submit?key=secret", json=state_payload(state_type))
        assert response.status_code == 200
        update = socket.receive_json()
        assert update["type"] == "state_update"
        assert update["device_name"] == "Test Device"
        assert update["state_file_type"] == state_type
        assert update["home_device"]["device_name"] == "Test Device"
        assert ("summary" in update) is (state_type != "OutputMetering")


def test_websocket_snapshot_and_subscription_cleanup(
    client: TestClient, store: Any
) -> None:
    """Existing devices are sent on connect and disconnect releases the subscription."""
    with client:
        client.post("/api/submit", json=state_payload())
        with client.websocket_connect("/ws") as socket:
            snapshot = socket.receive_json()
            assert snapshot["devices"][0]["device_name"] == "Test Device"
            assert len(store._queues) == 1  # ruff: ignore[private-member-access] - regression coverage of internal lifecycle contracts
        assert store._queues == []  # ruff: ignore[private-member-access] - regression coverage of internal lifecycle contracts


def test_websocket_external_deletion_and_missing_notification(
    client: TestClient, store: Any
) -> None:
    """Deleted devices are announced; notifications for unknown devices are ignored."""
    with client:
        client.post("/api/submit", json=state_payload())
        with client.websocket_connect("/ws") as socket:
            socket.receive_json()
            assert client.portal is not None
            client.portal.call(store._notify, "missing")  # ruff: ignore[private-member-access] - regression coverage of internal lifecycle contracts
            (store.state_data_dir / "Test Device.json").unlink()
            client.portal.call(store.check_external_changes)
            assert socket.receive_json() == {
                "type": "device_deleted",
                "device_name": "Test Device",
            }
