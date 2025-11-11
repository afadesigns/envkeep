from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from envkeep.cli import app

runner = CliRunner()


def test_plugin_discovery_and_fetching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    # 1. Create the remote JSON file
    remote_data_path = tmp_path / "remote.json"
    remote_data = {"REMOTE_VAR": "value_from_json"}
    remote_data_path.write_text(json.dumps(remote_data), encoding="utf-8")

    # 2. Create the local .env file
    env_file = tmp_path / ".env"
    env_file.write_text("LOCAL_VAR=local_value\nREMOTE_VAR=overridden_by_remote", encoding="utf-8")

    # 3. Create the envkeep.toml spec with a source URI
    spec_file = tmp_path / "envkeep.toml"
    spec_text = textwrap.dedent(
        f"""
        version = 1

        [[variables]]
        name = "LOCAL_VAR"
        type = "string"

        [[variables]]
        name = "REMOTE_VAR"
        type = "string"
        source = "json:{remote_data_path}#REMOTE_VAR"
        """,
    )
    spec_file.write_text(spec_text, encoding="utf-8")

    # 4. Run the check command
    result = runner.invoke(app, ["check", str(env_file)])

    # 5. Assert that the check passes and the remote value was used
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout

    # We can't directly inspect the values used in the check, but a successful
    # run implies the remote value was fetched and validated correctly.
    # To be more explicit, let's check a failure case.

    # 6. Test a failing case where the remote value is invalid
    spec_text_fail = textwrap.dedent(
        f"""
        version = 1

        [[variables]]
        name = "REMOTE_VAR"
        type = "int"  # This should fail as "value_from_json" is not an int
        source = "json:{remote_data_path}#REMOTE_VAR"
        """,
    )
    spec_file.write_text(spec_text_fail, encoding="utf-8")

    result_fail = runner.invoke(app, ["check", str(env_file)])

    assert result_fail.exit_code == 1
    assert "REMOTE_VAR" in result_fail.stdout
    assert "invalid" in result_fail.stdout
