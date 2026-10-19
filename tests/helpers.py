"""Reusable configuration, state payloads and isolated ASGI application factory."""

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from sc_foundation import SCLogger

from routes import register_routes
from state_store import StateStore
from websocket_manager import ConnectionManager

ROOT_DIR = Path(__file__).resolve().parents[1]
STATE_TYPES = ("PowerController", "LightingControl", "TempProbes", "OutputMetering")


class FakeConfig:
    """Mutable configuration with the same lookup contract as SCConfigManager."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.config_path: Path | None = None

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
        """Return a section or a setting with its supplied default.

        Returns:
            The configured section, setting, or supplied default.
        """
        section_data = self.values.get(section, {})
        return section_data if key is None else section_data.get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value for a test."""
        self.values.setdefault(section, {})[key] = value


def make_logger(logfile: Path | None, max_lines: int = 1000) -> SCLogger:
    """Create a real logger writing only to the test's temporary directory.

    Returns:
        The configured SCLogger instance.
    """
    return SCLogger(
        {
            "logfile_name": str(logfile) if logfile else None,
            "file_verbosity": "debug",
            "console_verbosity": "none",
            "max_lines": max_lines,
        }
    )


def make_client(
    config: FakeConfig,
    logger: SCLogger,
    store: Any = None,
    manager: Any = None,
    *,
    raise_server_exceptions: bool = True,
) -> TestClient:
    """Build routes against real templates without importing startup singletons.

    Returns:
        A TestClient for the isolated application.
    """
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")
    templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))
    register_routes(
        app,
        templates,
        config,
        logger,
        store if store is not None else StateStore(logger),
        manager if manager is not None else ConnectionManager(),
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def state_payload(
    state_type: str = "PowerController", name: str = "Test Device"
) -> dict[str, Any]:
    """Return a small valid wire payload for each supported producer.

    Returns:
        A new JSON-compatible payload for the requested producer.
    """
    data: dict[str, Any] = {
        "StateFileType": state_type,
        "SchemaVersion": 1,
        "DeviceName": name,
        "SaveTime": "2026-10-19T12:00:00+11:00",
    }
    if state_type == "PowerController":
        data.update(Output={"Type": "shelly", "IsOn": True}, Scheduler={})
    elif state_type == "LightingControl":
        data.pop("SaveTime")
        data.update(
            LastStateSaveTime="2026-10-19T12:00:00+11:00",
            RandomOffsets={},
            SwitchStates=[],
        )
    elif state_type == "TempProbes":
        data["TempProbeLogging"] = {"probes": [], "history": []}
    elif state_type == "OutputMetering":
        data.update(
            Summary={"FirstDate": "2026-10-01", "LastDate": "2026-10-19"}, Meters=[]
        )
    return data
