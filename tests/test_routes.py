"""Page routing, device/day selection, authentication and error responses."""

import asyncio
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from tests.helpers import STATE_TYPES, make_client, state_payload


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/summary",
        "/daily",
        "/system",
        "/config",
        "/log",
        "/log/content",
        "/log/download",
        "/api/submit",
    ],
)
@pytest.mark.parametrize("source", ["config", "environment"])
def test_access_control(
    client: TestClient,
    config: Any,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    source: str,
) -> None:
    """Every application endpoint enforces either configured or environment keys."""
    config.set("Website", "AccessKey", "config-key")
    if source == "environment":
        monkeypatch.setenv("VIEWER_ACCESS_KEY", "env-key")
    correct = "env-key" if source == "environment" else "config-key"
    method = client.post if path == "/api/submit" else client.get
    assert method(path).status_code == 403
    assert method(path, params={"key": "wrong"}).status_code == 403
    if source == "environment":
        assert method(path, params={"key": "config-key"}).status_code == 403
    response = method(path, params={"key": correct})
    assert response.status_code != 403


def test_empty_pages_and_daily_redirect(client: TestClient) -> None:
    """Empty installations show the no-state page and redirect daily views home."""
    assert cast("Any", client.get("/")).template.name == "no_state.html"
    assert cast("Any", client.get("/summary")).template.name == "no_state.html"
    response = client.get("/daily", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/"


@pytest.mark.parametrize(
    ("state_type", "template"),
    [
        ("PowerController", "summary_power.html"),
        ("LightingControl", "summary_lightingcontrol.html"),
        ("TempProbes", "temp_probes.html"),
        ("OutputMetering", "summary_output_metering.html"),
    ],
)
def test_summary_dispatch_and_home_render(
    client: TestClient, state_type: str, template: str
) -> None:
    """All supported producer payloads render their summary and home templates."""
    assert client.post("/api/submit", json=state_payload(state_type)).status_code == 200
    response = client.get("/summary")
    assert response.status_code == 200
    assert cast("Any", response).template.name == template
    assert "Test Device" in response.text
    assert cast("Any", client.get("/")).template.name == "home.html"


@pytest.mark.parametrize(
    ("params", "expected", "next_index"),
    [
        ({}, "Alpha", 1),
        ({"state_idx": "bad"}, "Alpha", 1),
        ({"state_idx": "-1"}, "Alpha", 1),
        ({"state_idx": "99"}, "Zulu", 0),
        ({"state_name": "Zulu"}, "Zulu", 0),
        ({"state_name": "missing"}, "Alpha", 1),
        ({"state_idx": "0", "state_name": "Zulu"}, "Alpha", 1),
    ],
)
def test_device_selection_and_next_wrap(
    client: TestClient, params: dict[str, str], expected: str, next_index: int
) -> None:
    """Device selection clamps indexes, supports URL names and wraps next-device links."""
    for name in ["Zulu", "Alpha"]:
        client.post("/api/submit", json=state_payload(name=name))
    response = client.get("/summary", params=params)
    view = cast("Any", response).context["page_data"]
    assert view["DeviceName"] == expected
    assert view["next_url"] == f"/summary?state_idx={next_index}"


@pytest.mark.parametrize("state_type", ["PowerController", "LightingControl"])
@pytest.mark.parametrize(
    ("day", "expected"), [(None, 0), ("bad", 0), ("-1", 0), ("99", 1), ("1", 1)]
)
def test_daily_selection(
    client: TestClient, state_type: str, day: str | None, expected: int
) -> None:
    """Daily pages clamp requested days and default to the latest history."""
    payload = state_payload(state_type)
    history = [{"Date": "2026-10-17"}, {"Date": "2026-10-18"}]
    if state_type == "PowerController":
        payload["Output"]["RunHistory"] = {"DailyData": history}
    else:
        payload["SwitchEvents"] = history
    client.post("/api/submit", json=payload)
    response = client.get("/daily", params={"day": day} if day is not None else {})
    assert response.status_code == 200
    assert cast("Any", response).template.name == (
        "daily_power.html"
        if state_type == "PowerController"
        else "daily_lightingcontrol.html"
    )
    assert cast("Any", response).context["page_data"]["CurrentDay"] == expected
    assert cast("Any", response).context["page_data"]["Date"] == (
        "18/10/2026" if expected == 0 else "17/10/2026"
    )


@pytest.mark.parametrize("state_type", STATE_TYPES)
def test_daily_without_history_redirects_to_summary(
    client: TestClient, config: Any, state_type: str
) -> None:
    """Devices without daily data return to the summary while retaining the key."""
    config.set("Website", "AccessKey", "secret")
    client.post("/api/submit?key=secret", json=state_payload(state_type))
    response = client.get("/daily?key=secret", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/summary?state_idx=0&key=secret"


def test_config_dump_is_escaped_and_handles_missing_file(
    client: TestClient, config: Any, tmp_path: Path
) -> None:
    """Config contents are HTML escaped, with readable absent/unreadable fallbacks."""
    assert "No config file." in client.get("/config").text
    config.config_path = tmp_path / "settings.yaml"
    config.config_path.write_text("Name: <script>alert(1)</script>\n")
    response = client.get("/config")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert str(config.config_path) in response.text
    config.config_path.unlink()
    assert "Could not read config file" in client.get("/config").text


def test_info_links_and_debug_message(client: TestClient, config: Any) -> None:
    """Navigation retains access keys and debug details appear only when enabled."""
    config.set("Website", "AccessKey", "secret")
    config.set("Website", "DebugMode", True)
    config.set("Website", "PageAutoRefresh", 15)
    config.set("Files", "LogFileVerbosity", "all")
    client.post("/api/submit?key=secret", json=state_payload())
    response = client.get("/summary?key=secret")
    assert (
        cast("Any", response).context["page_data"]["DebugMessage"]
        == "Devices: 1 | Log level: all"
    )
    assert cast("Any", response).context["page_data"]["RefreshDelay"] == 15
    assert "/config?key=secret" in response.text
    assert "/system?key=secret" in response.text
    config.set("Website", "DebugMode", False)
    assert (
        cast("Any", client.get("/summary?key=secret")).context["page_data"][
            "DebugMessage"
        ]
        is None
    )


def test_unsupported_state_and_not_found(client: TestClient, store: Any) -> None:
    """Unsupported stored states and missing URLs produce explicit error responses."""
    asyncio.run(store.save_and_update(state_payload("Other")))
    response = client.get("/summary")
    assert response.status_code == 500
    assert response.text == "Unsupported state type: Other"
    response = client.get("/missing")
    assert response.status_code == 404
    assert response.text == "Page not found."


def test_unhandled_error_response(
    config: Any, logger: Any, store: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unhandled view errors are logged and returned through the app error handler."""
    monkeypatch.setattr(
        store, "get_all_states", Mock(side_effect=RuntimeError("test failure"))
    )
    with make_client(
        config, logger, store, raise_server_exceptions=False
    ) as test_client:
        response = test_client.get("/")
    assert response.status_code == 500
    assert "Internal server error: test failure" in response.text
