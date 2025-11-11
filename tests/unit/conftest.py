from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from envkeep.config import Config


@pytest.fixture  # type: ignore[misc]
def mock_config(tmp_path: Path) -> Config:
    """A mock config that uses a temporary directory as the project root."""
    return Config(project_root=tmp_path)


@pytest.fixture  # type: ignore[misc]
def patch_config(monkeypatch: pytest.MonkeyPatch, mock_config: Config) -> MagicMock:
    """Patch the load_config function to return a mock config."""
    mock = MagicMock(return_value=mock_config)
    monkeypatch.setattr("envkeep.cli.load_config", mock)
    return mock


@pytest.fixture(autouse=True)  # type: ignore[misc]
def patch_console_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the console width to prevent truncation in tests."""
    monkeypatch.setattr("envkeep.cli.console.width", 1000)
