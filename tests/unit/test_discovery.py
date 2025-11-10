from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from envkeep.cli import app

runner = CliRunner()

# Resolve paths relative to the project root to ensure they are found
# during test runs, regardless of the current working directory.
PROJECT_ROOT = Path(__file__).parent.parent.parent
EXAMPLE_SPEC = (PROJECT_ROOT / "examples/basic/envkeep.toml").resolve()
DEV_ENV = (PROJECT_ROOT / "examples/basic/.env.dev").resolve()


def test_cli_check_discovers_spec_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    spec_file = tmp_path / "envkeep.toml"
    spec_file.write_text(EXAMPLE_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
    env_file = tmp_path / ".env.dev"
    env_file.write_text(DEV_ENV.read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["check", str(env_file)])

    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_check_discovers_spec_in_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    spec_file = tmp_path / "envkeep.toml"
    spec_file.write_text(EXAMPLE_SPEC.read_text(encoding="utf-8"), encoding="utf-8")

    sub_dir = tmp_path / "sub"
    sub_dir.mkdir()
    monkeypatch.chdir(sub_dir)

    env_file = sub_dir / ".env.dev"
    env_file.write_text(DEV_ENV.read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["check", str(env_file)])

    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_check_fails_when_no_spec_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env.dev"
    env_file.write_text(DEV_ENV.read_text(encoding="utf-8"), encoding="utf-8")

    result = runner.invoke(app, ["check", str(env_file)])

    assert result.exit_code != 0
    assert "spec file not found (envkeep.toml)" in result.stderr


def test_cli_spec_option_overrides_discovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # Create a dummy spec in the current directory that would cause a failure
    dummy_spec = tmp_path / "envkeep.toml"
    dummy_spec.write_text('[[variables]]\nname = "UNUSED_VAR"\nrequired = true', encoding="utf-8")

    env_file = tmp_path / ".env.dev"
    env_file.write_text(DEV_ENV.read_text(encoding="utf-8"), encoding="utf-8")

    # Explicitly point to the correct, external spec
    result = runner.invoke(app, ["check", str(env_file), "--spec", str(EXAMPLE_SPEC)])

    assert result.exit_code == 0
    assert "All checks passed" in result.stdout
