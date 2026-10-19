"""System page deployment metadata and host metrics."""

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sc_foundation import SCCommon

from tests.helpers import state_payload

# ---- System page ----

_DEPLOYMENT_INFO = {
    "name": "PowerControllerViewer",
    "version": "9.8.7",
    "description": "Test",
    "git_branch": "feature/test-branch",
    "git_tag": None,
    "git_remote": "https://secret-token@github.com/example/repo.git",
    "git_status": "Ahead",
    "git_changes": 3,
}


def test_system_page_shows_version_and_git(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The system page shows the app version and git branch/status/changes."""
    monkeypatch.setattr(SCCommon, "get_deployment_info", lambda: dict(_DEPLOYMENT_INFO))
    body = client.get("/system").text

    assert "Application version" in body
    assert "9.8.7" in body
    assert "feature/test-branch" in body
    assert "Ahead" in body
    assert "Uncommitted changes" in body
    # The remote URL can embed credentials, so it must never be shown.
    assert "secret-token" not in body
    assert 'href="/log"' in body


def test_system_page_without_git(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git rows are omitted when the app isn't running from a git checkout."""
    info = dict(
        _DEPLOYMENT_INFO, git_branch=None, git_status="Unknown", git_changes=None
    )
    monkeypatch.setattr(SCCommon, "get_deployment_info", lambda: info)
    body = client.get("/system").text

    assert "9.8.7" in body
    assert "Git branch" not in body
    assert "Uncommitted changes" not in body


@pytest.mark.parametrize(
    ("seconds", "uptime"), [(60, "1m"), (3660, "1h 1m"), (90060, "1d 1h 1m")]
)
def test_system_metrics_and_loaded_device_count(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, seconds: int, uptime: str
) -> None:
    """Host metrics and uptime units render alongside the actual loaded-device count."""
    client.post("/api/submit", json=state_payload())
    monkeypatch.setattr("routes.time", SimpleNamespace(time=lambda: seconds))
    response = client.get("/system")
    assert response.status_code == 200
    info = cast("Any", response).context["system_info"]
    assert info["Number of data files loaded"] == 1
    assert info["Uptime"] == uptime
    assert info["Memory used"] == "50%"
    assert info["CPU load"] == "25%"
