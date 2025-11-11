from __future__ import annotations

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

from envkeep.config import Config


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Return a mock Config instance."""
    return Config(project_root=tmp_path)


@pytest.fixture
def patch_config(
    monkeypatch: pytest.MonkeyPatch,
    mock_config: Config,
) -> Generator[MagicMock, None, None]:
    """Patch load_config to return a mock Config instance."""
    mock_load_config = MagicMock(return_value=mock_config)
    monkeypatch.setattr("envkeep.cli.load_config", mock_load_config)
    yield mock_load_config
