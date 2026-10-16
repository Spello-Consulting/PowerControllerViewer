"""Shared pytest fixtures for the PowerControllerViewer test suite."""

import sys
from pathlib import Path

import pytest

# Ensure src/ is importable without PYTHONPATH being set
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def _clear_access_key_env(monkeypatch):
    """Prevent the shell environment from leaking an access key into tests."""
    monkeypatch.delenv("VIEWER_ACCESS_KEY", raising=False)
