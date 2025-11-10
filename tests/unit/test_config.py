from __future__ import annotations

from pathlib import Path
import textwrap

from typer.testing import CliRunner

from envkeep.cli import app

runner = CliRunner()


def test_config_from_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    spec_file = config_dir / "envkeep.toml"
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    env_file = profile_dir / ".env"

    # 1. Create pyproject.toml with envkeep config
    pyproject_content = textwrap.dedent(
        f"""
        [tool.envkeep]
        spec = "{spec_file.relative_to(tmp_path)}"
        profile_base = "{profile_dir.relative_to(tmp_path)}"
        """
    )
    (tmp_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")

    # 2. Create the spec and env file
    spec_text = textwrap.dedent(
        f"""
        version = 1
        [[variables]]
        name = "MY_VAR"
        type = "string"

        [[profiles]]
        name = "test"
        env_file = "{env_file.name}"
        """
    )
    spec_file.write_text(spec_text, encoding="utf-8")
    env_file.write_text("MY_VAR=value1", encoding="utf-8")

    # 3. Run doctor, it should find everything via pyproject.toml
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout

    # 4. Test CLI argument override
    other_spec_file = tmp_path / "other.toml"
    other_spec_file.write_text(spec_text, encoding="utf-8")
    result_override = runner.invoke(app, ["doctor", "--spec", str(other_spec_file)])
    assert result_override.exit_code == 0
    assert "All checks passed" in result_override.stdout
