"""Log viewer rendering, incremental reads, downloads and access control."""

import pytest
from fastapi.testclient import TestClient
from sc_foundation import SCLogger

from tests.helpers import FakeConfig, make_client, make_logger

# ---- Log viewer ----


def test_log_page_shows_contents(client: TestClient, logger: SCLogger) -> None:
    """The log page renders the log file contents, HTML-escaped."""
    response = client.get("/log")

    assert response.status_code == 200
    body = response.text
    assert "first log line" in body
    assert "&lt;b&gt;tagged&lt;/b&gt;" in body
    assert logger.get_logfile_path() in body
    assert 'id="log-live"' in body
    assert "/log/download" in body
    assert "/static/log.js" in body


def test_log_content_incremental(client: TestClient, logger: SCLogger) -> None:
    """/log/content returns only new lines when given the previous position."""
    first = client.get("/log/content").json()
    assert first["reset"] is True
    assert "first log line" in first["text"]

    logger.log_message("a newer line", "summary")
    second = client.get(
        "/log/content",
        params={"generation": first["generation"], "offset": first["offset"]},
    ).json()

    assert second["reset"] is False
    assert "a newer line" in second["text"]
    assert "first log line" not in second["text"]


def test_log_content_resets_after_trim(client: TestClient, logger: SCLogger) -> None:
    """After the log is trimmed the client is told to replace its content."""
    first = client.get("/log/content").json()

    for i in range(10):
        logger.log_message(f"filler {i}", "summary")
    logger.trim_logfile()

    second = client.get(
        "/log/content",
        params={"generation": first["generation"], "offset": first["offset"]},
    ).json()

    assert second["reset"] is True
    assert second["text"] == logger.read_logfile()


def test_log_download(client: TestClient, logger: SCLogger) -> None:
    """/log/download returns the log file as an attachment."""
    response = client.get("/log/download")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="app.log"'
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == logger.read_logfile()


def test_log_pages_when_file_logging_disabled(config: FakeConfig) -> None:
    """With file logging off the page explains why and download is a 404."""
    test_client = make_client(config, make_logger(None))

    page = test_client.get("/log")
    assert page.status_code == 200
    assert "File logging is not enabled" in page.text
    assert "/static/log.js" not in page.text
    assert test_client.get("/log/download").status_code == 404
    assert not test_client.get("/log/content").json()["text"]


@pytest.mark.parametrize("use_env", [False, True])
def test_log_endpoints_require_access_key(
    client: TestClient,
    config: FakeConfig,
    monkeypatch: pytest.MonkeyPatch,
    use_env: bool,
) -> None:
    """Every log endpoint is gated by the access key (config or environment)."""
    if use_env:
        monkeypatch.setenv("VIEWER_ACCESS_KEY", "letmein")
    else:
        config.set("Website", "AccessKey", "letmein")

    for path in ("/log", "/log/content", "/log/download"):
        assert client.get(path).status_code == 403
        assert client.get(path, params={"key": "wrong"}).status_code == 403
        assert client.get(path, params={"key": "letmein"}).status_code == 200


def test_log_page_links_carry_access_key(
    client: TestClient, config: FakeConfig
) -> None:
    """Download and back links, and the live-update script, keep the access key."""
    config.set("Website", "AccessKey", "letmein")
    body = client.get("/log", params={"key": "letmein"}).text

    assert "/log/download?key=letmein" in body
    assert "/system?key=letmein" in body
    assert 'window.__ACCESS_KEY__ = "letmein"' in body
