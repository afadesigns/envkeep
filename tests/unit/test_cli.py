from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from envkeep.cli import app
from envkeep.cli import check as cli_check
from envkeep.cli import diff as cli_diff
from envkeep.cli import doctor as cli_doctor

runner = CliRunner()
EXAMPLE_SPEC = Path("examples/basic/envkeep.toml")
DEV_ENV = Path("examples/basic/.env.dev")
PROD_ENV = Path("examples/basic/.env.prod")


def test_cli_diff_json_output(tmp_path: Path) -> None:
    left = tmp_path / "left.env"
    right = tmp_path / "right.env"
    left.write_text(DEV_ENV.read_text(), encoding="utf-8")
    right.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost:5432/devdb",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=DUMMY_TOKEN_VALUE_THAT_IS_32_CHARS",
            ],
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "diff",
            str(left),
            str(right),
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["report"]
    assert payload["summary"]
    assert payload["summary"]["by_kind"]["changed"] == 4
    assert payload["summary"]["non_empty_kinds"] == ["changed"]
    assert payload["summary"]["variables"] == ["ALLOWED_HOSTS", "API_TOKEN", "DATABASE_URL", "DEBUG"]
    assert payload["summary"]["top_variables"][0][0] == "ALLOWED_HOSTS"
    report_payload = payload["report"]
    assert report_payload["is_clean"] is False
    assert report_payload["by_kind"]["missing"] == 0
    assert report_payload["variables"] == ["ALLOWED_HOSTS", "API_TOKEN", "DATABASE_URL", "DEBUG"]
    assert report_payload["top_variables"][0][0] == "ALLOWED_HOSTS"
