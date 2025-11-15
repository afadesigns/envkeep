from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from envkeep.cli import _fetch_remote_values
from envkeep.report import ValidationReport
from envkeep.spec import EnvSpec


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_fetch_remote_values_parallel(caplog):
    """Verify that remote values are fetched in parallel."""
    spec = EnvSpec.from_dict(
        {
            "variables": [
                {"name": "VAR1", "source": "mock1:uri1"},
                {"name": "VAR2", "source": "mock2:uri2"},
            ],
        },
    )

    mock_backend1 = MagicMock()
    mock_backend1.fetch.return_value = {"VAR1": "value1"}
    mock_backend2 = MagicMock()
    mock_backend2.fetch.return_value = {"VAR2": "value2"}

    with patch(
        "envkeep.cli.load_backends",
        return_value={"mock1": mock_backend1, "mock2": mock_backend2},
    ):
        report = ValidationReport()
        with caplog.at_level(logging.INFO):
            result = _fetch_remote_values(spec, report, strict_plugins=False)

    assert result == {"VAR1": "value1", "VAR2": "value2"}
    assert mock_backend1.fetch.call_count == 1
    assert mock_backend2.fetch.call_count == 1


def test_fetch_remote_values_with_errors(caplog):
    """Verify that errors in backends are handled gracefully."""
    spec = EnvSpec.from_dict(
        {
            "variables": [
                {"name": "VAR1", "source": "mock1:uri1"},
                {"name": "VAR2", "source": "mock2:uri2"},
            ],
        },
    )
    mock_backend1 = MagicMock()
    mock_backend1.fetch.return_value = {"VAR1": "value1"}
    mock_backend2 = MagicMock()
    mock_backend2.fetch.side_effect = Exception("Something went wrong")

    with patch(
        "envkeep.cli.load_backends",
        return_value={"mock1": mock_backend1, "mock2": mock_backend2},
    ):
        report = ValidationReport()
        with caplog.at_level(logging.ERROR):
            result = _fetch_remote_values(spec, report, strict_plugins=False)

    assert result == {"VAR1": "value1"}
    assert "Plugin mock2 failed to fetch secrets" in caplog.text
