from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

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
PROD_ENV_ABS = PROD_ENV.resolve()


def test_cli_init_creates_spec(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    output = tmp_path / "envkeep.toml"
    result = runner.invoke(
        app,
        [
            "init",
            str(env_file),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "FOO" in content
    assert "BAZ" in content


def test_cli_init_confirms_overwrite(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n", encoding="utf-8")
    output = tmp_path / "envkeep.toml"
    output.write_text("initial", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "init",
            str(env_file),
            "--output",
            str(output),
        ],
        input="n\n",
    )
    assert "Aborted" in result.stdout
    assert output.read_text(encoding="utf-8") == "initial"
    force_result = runner.invoke(
        app,
        [
            "init",
            str(env_file),
            "--output",
            str(output),
            "--force",
        ],
    )
    assert force_result.exit_code == 0
    assert "FOO" in output.read_text(encoding="utf-8")


def test_cli_check_success() -> None:
    result = runner.invoke(app, ["check", str(DEV_ENV), "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_check_failure(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=http://example.com\n", encoding="utf-8")
    result = runner.invoke(app, ["check", str(env_file), "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 1
    assert "API_TOKEN" in result.stdout
    assert "Errors: 1" in result.stdout


def test_cli_check_json_summary() -> None:
    result = runner.invoke(
        app,
        [
            "check",
            str(DEV_ENV),
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["severity_totals"]["warning"] == 0


def test_cli_check_rejects_negative_summary_top(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    with pytest.raises(typer.Exit) as excinfo:
        cli_check(
            env_file=env_file,
            spec=EXAMPLE_SPEC,
            output_format="text",
            allow_extra=False,
            fail_on_warnings=False,
            summary_top=-1,
        )
    assert excinfo.value.exit_code == 2
    captured = capsys.readouterr()
    assert "summary limit must be non-negative" in captured.err


def test_cli_rejects_unknown_format(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "check",
            str(env_file),
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "yaml",
        ],
    )
    assert result.exit_code == 2
    assert "Invalid value for '--format'" in result.stdout


def test_cli_check_fail_on_warnings(tmp_path: Path) -> None:
    env_file = tmp_path / "warn.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA=value",
            ],
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "check",
            str(env_file),
            "--spec",
            str(EXAMPLE_SPEC),
            "--fail-on-warnings",
        ],
    )
    assert result.exit_code == 1
    assert "EXTRA" in result.stdout


def test_cli_diff_detects_changes(tmp_path: Path) -> None:
    left = tmp_path / "left.env"
    right = tmp_path / "right.env"
    left.write_text(DEV_ENV.read_text(), encoding="utf-8")
    right.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost:5432/devdb",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
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
        ],
    )
    assert result.exit_code == 1
    assert "Total differences" in result.stdout


def test_cli_generate_stdout() -> None:
    result = runner.invoke(app, ["generate", "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 0
    assert "DATABASE_URL=" in result.stdout


def test_cli_generate_no_redact_secrets() -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(EXAMPLE_SPEC),
            "--no-redact-secrets",
        ],
    )
    assert result.exit_code == 0
    assert "API_TOKEN=<redacted>" in result.stdout
    assert "API_TOKEN=***" not in result.stdout


def test_cli_generate_accepts_spec_from_stdin() -> None:
    spec_text = EXAMPLE_SPEC.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            "-",
        ],
        input=spec_text,
    )
    assert result.exit_code == 0
    assert "DATABASE_URL=" in result.stdout


def test_cli_doctor_resolves_relative_profiles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_config: MagicMock,
) -> None:
    spec_dir = patch_config.return_value.project_root / "spec"
    env_dir = patch_config.return_value.project_root / "env"
    home_dir = patch_config.return_value.project_root / "home"
    spec_dir.mkdir()
    env_dir.mkdir()
    home_dir.mkdir()
    env_file = env_dir / "app.env"
    env_file.write_text("FOO=value\n", encoding="utf-8")
    home_env = home_dir / "home.env"
    home_env.write_text("FOO=value\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home_dir))
    spec_file = spec_dir / "envkeep.toml"
    spec_file.write_text(
        textwrap.dedent(
            """
            version = 1

            [[variables]]
            name = "FOO"

            [[profiles]]
            name = "app"
            env_file = "../env/app.env"

            [[profiles]]
            name = "app-home"
            env_file = "~/home.env"
            """,
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            str(spec_file),
            "--profile-base",
            str(spec_dir),
        ],
    )
    print(result.output)
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_doctor_profile_base_override(tmp_path: Path) -> None:
    profile_base = tmp_path / "profiles"
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[profiles]]
        name = "app"
        env_file = "env/app.env"
        """,
    )
    env_dir = profile_base / "env"
    env_dir.mkdir(parents=True)
    env_file = env_dir / "app.env"
    env_file.write_text("FOO=value\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            "-",
            "--profile-base",
            str(profile_base),
        ],
        input=spec_text,
    )
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_generate_writes_nested_path(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "example.env"
    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(EXAMPLE_SPEC),
            "--output",
            str(target),
        ],
    )
    assert result.exit_code == 0
    contents = target.read_text(encoding="utf-8")
    assert "DATABASE_URL=" in contents


def test_cli_doctor_all(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = EXAMPLE_SPEC.read_text()
    spec_copy = tmp_path / "envkeep.toml"
    missing = tmp_path / "missing.env"
    spec_copy.write_text(
        spec_text.replace(".env.dev", str(env_file)).replace(".env.prod", str(missing)),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", "--spec", str(spec_copy)])
    assert result.exit_code == 1
    assert "missing env file" in result.stdout


def test_cli_doctor_json_output(tmp_path: Path, patch_config: MagicMock) -> None:
    env_file = patch_config.return_value.project_root / "dev.env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace(".env.dev", str(env_file))
        .replace(".env.prod", str(env_file))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            str(spec_copy),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["profiles"]
    profile = payload["profiles"][0]
    assert profile["report"]["is_success"] is True
    assert profile["summary"]["severity_totals"]["warning"] == 0
    assert profile["warnings"]["total"] == 0
    assert payload["summary"]["severity_totals"]["warning"] == 0
    assert profile["env_file"] == str(env_file)
    assert profile["resolved_env_file"] == str(env_file)
    assert payload["summary"]["profile_base_dir"] == str(spec_copy.parent.resolve())


def test_cli_doctor_fail_on_warnings(tmp_path: Path) -> None:
    env_file = tmp_path / "warn.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA=value",
            ],
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace(".env.dev", str(env_file))
        .replace(".env.prod", str(PROD_ENV_ABS))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            str(spec_copy),
            "--profile",
            "development",
            "--fail-on-warnings",
        ],
    )
    assert result.exit_code == 1


def test_cli_reports_toml_parse_location(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    bad_spec = tmp_path / "broken.toml"
    bad_spec.write_text("version =\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "check",
            str(env_file),
            "--spec",
            str(bad_spec),
        ],
    )
    assert result.exit_code != 0
    assert "failed to parse spec" in result.stdout
    assert "line 1" in result.stdout


def test_cli_doctor_json_warnings(tmp_path: Path) -> None:
    env_file = tmp_path / "warn.env"
    env_file.write_text(
        "\n".join(
            [
                "BROKEN",
                "DATABASE_URL=postgresql://localhost/dev",
                "DATABASE_URL=postgresql://localhost/prod",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA=value",
            ],
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace(".env.dev", str(env_file))
        .replace(".env.prod", str(PROD_ENV_ABS))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            str(spec_copy),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    profile = payload["profiles"][0]
    warnings = profile["warnings"]
    assert warnings["total"] == 3
    assert warnings["extra_variables"] == ["EXTRA"]
    assert warnings["duplicates"] == ["DATABASE_URL"]
    assert warnings["invalid_lines"][0]["line"].startswith("line")
    assert profile["summary"]["issue_count"] == 3
    assert profile["summary"]["has_warnings"] is True
    assert profile["summary"]["has_errors"] is False
    assert profile["summary"]["severity_totals"]["warning"] == 3
    assert profile["summary"]["non_empty_severities"] == ["warning"]
    assert profile["summary"]["variables"]
    assert profile["summary"]["top_variables"][0][0] == "DATABASE_URL"
    assert profile["summary"]["variables_by_severity"]["warning"]
    assert payload["summary"]["severity_totals"]["warning"] == 3
    assert payload["summary"]["variables"]
    assert payload["summary"]["non_empty_severities"] == ["warning"]
    assert payload["summary"]["top_variables"]
    summary_codes = dict(payload["summary"]["most_common_codes"])
    assert summary_codes.get("extra") == 1
    top_variables = dict(payload["summary"]["top_variables"])
    assert top_variables.get("DATABASE_URL") == 1
    aggregated = payload["warnings"]
    assert aggregated["duplicates"] == ["DATABASE_URL"]
    assert aggregated["extra_variables"] == ["EXTRA"]
    assert aggregated["invalid_lines"]
    assert aggregated["invalid_lines"][0]["profile"] == "development"
    assert aggregated["invalid_lines"][0]["line"].startswith("line")


def test_cli_doctor_json_invalid_lines_sorted(tmp_path: Path) -> None:
    base_dir = tmp_path / "profiles"
    env_dir = base_dir / "env"
    env_dir.mkdir(parents=True)
    first_env = env_dir / "first.env"
    first_env.write_text(
        "\n".join(
            [
                "# comment",
                "BROKEN",
                "FOO=value",
                "BAR=value",
                "BADLINE",
            ],
        ),
        encoding="utf-8",
    )
    second_env = env_dir / "second.env"
    second_env.write_text(
        "\n".join(
            [
                "FOO=value",
                "BAR=value",
                "INVALID",
            ],
        ),
        encoding="utf-8",
    )
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[variables]]
        name = "BAR"

        [[profiles]]
        name = "second"
        env_file = "env/second.env"

        [[profiles]]
        name = "first"
        env_file = "env/first.env"
        """,
    )
    spec_file = base_dir / "envkeep.toml"
    spec_file.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            str(spec_file),
            "--format",
            "json",
            "--profile-base",
            str(base_dir),
        ],
    )
    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    invalid_lines = payload["warnings"]["invalid_lines"]
    assert [entry["profile"] for entry in invalid_lines] == ["first", "first", "second"]
    assert [entry["line"] for entry in invalid_lines] == ["line 2", "line 5", "line 3"]


def test_cli_doctor_json_summary_top_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / "warn.env"
    env_file.write_text(
        "\n".join(
            [
                "BROKEN",
                "DATABASE_URL=postgresql://localhost/dev",
                "DATABASE_URL=postgresql://localhost/prod",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA=value",
            ],
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace(".env.dev", str(env_file))
        .replace(".env.prod", str(PROD_ENV_ABS))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    with pytest.raises(typer.Exit) as excinfo:
        cli_doctor(
            spec=spec_copy,
            profile="all",
            allow_extra=False,
            output_format="json",
            fail_on_warnings=False,
            summary_top=0,
        )
    assert excinfo.value.exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    profile = payload["profiles"][0]
    assert profile["summary"]["top_variables"] == []
    assert profile["summary"]["most_common_codes"] == []
    assert payload["summary"]["top_variables"] == []
    assert payload["summary"]["most_common_codes"] == []
    warnings = payload["warnings"]
    assert warnings["duplicates"] == ["DATABASE_URL"]
    assert warnings["extra_variables"] == ["EXTRA"]
    assert warnings["invalid_lines"][0]["profile"] == "development"


def test_cli_check_json_summary_reports_issue_flags(tmp_path: Path) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ],
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "check",
            str(env_file),
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    summary = payload["summary"]
    assert (
        summary["issue_count"]
        == summary["severity_totals"]["error"]
        + summary["severity_totals"]["warning"]
        + summary["severity_totals"]["info"]
    )
    assert summary["has_errors"] is True
    assert summary["has_warnings"] is True
    assert summary["has_info"] is False
    assert summary["non_empty_severities"] == ["error", "warning"]
    assert summary["variables"]
    assert summary["top_variables"]
    assert summary["variables_by_severity"]["error"]
    report_payload = payload["report"]
    assert report_payload["issue_count"] == summary["issue_count"]
    assert report_payload["variables"]
    assert report_payload["most_common_codes"][0][0] in {"duplicate", "extra"}
    assert report_payload["top_variables"]


def test_cli_check_summary_top_zero_suppresses_impacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ],
        ),
        encoding="utf-8",
    )
    with pytest.raises(typer.Exit) as excinfo:
        cli_check(
            env_file=env_file,
            spec=EXAMPLE_SPEC,
            output_format="text",
            allow_extra=False,
            fail_on_warnings=False,
            summary_top=0,
        )
    assert excinfo.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Impacted:" not in output


def test_cli_check_json_respects_summary_top(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ],
        ),
        encoding="utf-8",
    )
    with pytest.raises(typer.Exit) as excinfo:
        cli_check(
            env_file=env_file,
            spec=EXAMPLE_SPEC,
            output_format="json",
            allow_extra=False,
            fail_on_warnings=False,
            summary_top=1,
        )
    assert excinfo.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["summary"]["top_variables"]) == 1
    assert len(payload["report"]["top_variables"]) == 1
    assert payload["summary"]["top_variables"][0][0] == "API_TOKEN"


def test_cli_doctor_text_highlights_impacted_variables(tmp_path: Path) -> None:
    env_file = tmp_path / "warn.env"
    env_file.write_text(
        "\n".join(
            [
                "BROKEN",
                "DATABASE_URL=postgresql://localhost/dev",
                "DATABASE_URL=postgresql://localhost/prod",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA=value",
            ],
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace(".env.dev", str(env_file))
        .replace(".env.prod", str(PROD_ENV_ABS))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--spec", str(spec_copy)])
    assert result.exit_code == 0
    assert "Impacted variables:" in result.stdout
    assert "Top impacted variables:" in result.stdout


def test_cli_doctor_reports_summary(tmp_path: Path, patch_config: MagicMock) -> None:
    dev_env = patch_config.return_value.project_root / "dev.env"
    dev_env.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = (
        EXAMPLE_SPEC.read_text(encoding="utf-8")
        .replace(".env.dev", str(dev_env))
        .replace(".env.prod", ".env.prod")
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--spec", str(spec_copy)])
    assert result.exit_code == 1
    assert "Doctor Summary" in result.stdout
    assert "Profiles checked: 1/2" in result.stdout
    assert "Missing profiles: 1" in result.stdout
    assert "Total errors: 0" in result.stdout
    assert "Total warnings: 0" in result.stdout
    assert "Total info: 0" in result.stdout
    assert (
        "Warnings breakdown: Duplicates: 0 · Extra variables: 0 · Invalid lines: 0" in result.stdout
    )
    assert "Impacted variables:" in result.stdout
    dev_env_str = str(dev_env)
    missing_env = str(tmp_path / ".env.prod")
    normalized_output = " ".join(result.stdout.split())
    assert f"• development: {dev_env_str} -> {dev_env_str}" in normalized_output
    assert f"• production: .env.prod -> {missing_env} (missing)" in normalized_output


def test_cli_doctor_profile_base_missing_dir(tmp_path: Path) -> None:
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[profiles]]
        name = "app"
        env_file = "env/app.env"
        """,
    )
    missing_base = tmp_path / "missing"
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            "-",
            "--profile-base",
            str(missing_base),
        ],
        input=spec_text,
    )
    assert result.exit_code != 0
    normalized_stderr = " ".join(result.stderr.lower().split())
    assert "profile base" in normalized_stderr
    assert "not exist" in normalized_stderr


def test_cli_doctor_profile_base_not_directory(tmp_path: Path) -> None:
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[profiles]]
        name = "app"
        env_file = "env/app.env"
        """,
    )
    file_base = tmp_path / "base.txt"
    file_base.write_text("not a directory", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "doctor",
            "--spec",
            "-",
            "--profile-base",
            str(file_base),
        ],
        input=spec_text,
    )
    assert result.exit_code != 0
    normalized_stderr = " ".join(result.stderr.lower().split())
    assert "profile base" in normalized_stderr
    assert "not a directory" in normalized_stderr


def test_cli_check_reads_from_stdin() -> None:
    stdin_content = "\n".join(
        [
            "DATABASE_URL=postgresql://localhost/dev",
            "DEBUG=false",
            "ALLOWED_HOSTS=localhost",
            "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
        ],
    )
    result = runner.invoke(
        app,
        [
            "check",
            "-",
            "--spec",
            str(EXAMPLE_SPEC),
        ],
        input=stdin_content,
    )
    assert result.exit_code == 0


def test_cli_diff_reads_from_stdin(tmp_path: Path) -> None:
    right = tmp_path / "right.env"
    right.write_text(DEV_ENV.read_text(), encoding="utf-8")
    stdin_content = DEV_ENV.read_text()
    result = runner.invoke(
        app,
        [
            "diff",
            "-",
            str(right),
            "--spec",
            str(EXAMPLE_SPEC),
        ],
        input=stdin_content,
    )
    assert result.exit_code == 0


def test_cli_diff_json_summary(tmp_path: Path) -> None:
    right = tmp_path / "right.env"
    right.write_text(DEV_ENV.read_text(), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "diff",
            str(DEV_ENV),
            str(right),
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.stderr
    stdout = result.stdout or result.output
    assert stdout
    payload = json.loads(stdout)
    assert payload["summary"]["is_clean"] is True
    assert payload["summary"]["by_kind"]["changed"] == 0
    assert payload["summary"]["non_empty_kinds"] == []
    assert payload["summary"]["variables"] == []
    assert payload["summary"]["top_variables"] == []
    report_payload = payload["report"]
    assert report_payload["is_clean"] is True
    assert report_payload["by_kind"]["missing"] == 0
    assert report_payload["variables"] == []
    assert report_payload["top_variables"] == []


def test_cli_diff_summary_top_zero_omits_impacted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    left = tmp_path / "left.env"
    right = tmp_path / "right.env"
    left.write_text(DEV_ENV.read_text(), encoding="utf-8")
    right.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost:5432/devdb",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost,api.local",
                "EXTRA_VAR=value",
            ],
        ),
        encoding="utf-8",
    )
    with pytest.raises(typer.Exit) as excinfo:
        cli_diff(
            first=left,
            second=right,
            spec=EXAMPLE_SPEC,
            output_format="text",
            summary_top=0,
        )
    assert excinfo.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Impacted:" not in output


def test_cli_diff_text_summary_breakdown(tmp_path: Path) -> None:
    left = tmp_path / "left.env"
    right = tmp_path / "right.env"
    left.write_text(DEV_ENV.read_text(), encoding="utf-8")
    right.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost:5432/devdb",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost,api.local",
                "EXTRA_VAR=value",
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
        ],
    )
    assert result.exit_code == 1
    assert "Missing: 1" in result.stdout
    assert "Extra: 1" in result.stdout
    assert "Changed: 2" in result.stdout
    assert "Impacted:" in result.stdout
    assert "Missing\n" in result.stdout
    assert "Extra\n" in result.stdout
    assert "Changed\n" in result.stdout


def test_cli_check_supports_spec_from_stdin(tmp_path: Path) -> None:
    env_file = tmp_path / "from-stdin.env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = EXAMPLE_SPEC.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "check",
            str(env_file),
            "--spec",
            "-",
        ],
        input=spec_text,
    )
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_check_rejects_double_stdin(tmp_path: Path) -> None:
    spec_text = EXAMPLE_SPEC.read_text(encoding="utf-8")
    env_text = DEV_ENV.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "check",
            "-",
            "--spec",
            "-",
        ],
        input=spec_text + env_text,
    )
    assert result.exit_code != 0
    assert "cannot read both spec and environment from stdin" in result.stderr


def test_cli_diff_rejects_spec_and_env_stdin(tmp_path: Path) -> None:
    left = tmp_path / "left.env"
    left.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = EXAMPLE_SPEC.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "diff",
            "-",
            str(left),
            "--spec",
            "-",
        ],
        input=spec_text,
    )
    assert result.exit_code != 0
    assert "cannot combine spec from stdin" in result.stderr


def test_cli_generate_docs() -> None:
    result = runner.invoke(app, ["generate-docs", "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 0
    assert "| Variable | Type | Required | Description | Default |" in result.stdout
    assert "| DATABASE_URL |" in result.stdout


def test_cli_generate_docs_writes_to_file(tmp_path: Path) -> None:
    output = tmp_path / "docs.md"
    result = runner.invoke(
        app,
        [
            "generate-docs",
            "--spec",
            str(EXAMPLE_SPEC),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "| Variable | Type | Required | Description | Default |" in content
    assert "| DATABASE_URL |" in content


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "envkeep version:" in result.stdout


def test_cli_generate_schema() -> None:
    result = runner.invoke(app, ["generate-schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert "variables" in schema["properties"]
    assert "profiles" in schema["properties"]


def test_cli_generate_schema_writes_to_file(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    result = runner.invoke(app, ["generate-schema", "--output", str(output)])
    assert result.exit_code == 0
    assert output.exists()
    schema = json.loads(output.read_text(encoding="utf-8"))
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_cli_inspect_json_output(patch_config: MagicMock) -> None:
    spec_file = patch_config.return_value.project_root / "envkeep.toml"
    spec_file.write_text(EXAMPLE_SPEC.read_text(), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "inspect",
            "--spec",
            str(spec_file),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["version"] == 1
    assert (
        Path(payload["profile_base_dir"]).resolve()
        == patch_config.return_value.project_root.resolve()
    )
    first_variable = payload["variables"][0]
    assert first_variable["name"] == "DATABASE_URL"
    assert "profiles" in payload
    first_profile = payload["profiles"][0]
    expected_path = (
        patch_config.return_value.project_root / Path(first_profile["env_file"]).expanduser()
    ).resolve()
    assert first_profile["resolved_env_file"] == str(expected_path)


def test_cli_inspect_text_shows_resolved_paths(patch_config: MagicMock) -> None:
    base = patch_config.return_value.project_root
    env_dir = base / "env"
    env_dir.mkdir()
    env_file = env_dir / "app.env"
    env_file.write_text("FOO=value\n", encoding="utf-8")
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[profiles]]
        name = "app"
        env_file = "env/app.env"
        description = "Primary"
        """,
    )
    spec_file = base / "envkeep.toml"
    spec_file.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "inspect",
            "--spec",
            str(spec_file),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["profiles"][0]["resolved_env_file"] == str(env_file.resolve())


def test_cli_inspect_profile_base_override(tmp_path: Path) -> None:
    env_dir = tmp_path / "alternate" / "env"
    env_dir.mkdir(parents=True)
    env_file = env_dir / "app.env"
    env_file.write_text("FOO=value\n", encoding="utf-8")
    spec_text = textwrap.dedent(
        """
        version = 1

        [[variables]]
        name = "FOO"

        [[profiles]]
        name = "app"
        env_file = "env/app.env"
        """,
    )
    result = runner.invoke(
        app,
        [
            "inspect",
            "--spec",
            "-",
            "--format",
            "json",
            "--profile-base",
            str(env_dir.parent),
        ],
        input=spec_text,
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    profile = payload["profiles"][0]
    assert profile["resolved_env_file"] == str(env_file)
    assert payload["profile_base_dir"] == str(env_dir.parent.resolve())

    def test_cli_check_orders_severity_and_reports_info(tmp_path: Path) -> None:
        env_file = tmp_path / "bad.env"
        env_file.write_text(
            "\n".join(
                [
                    "DATABASE_URL=postgresql://localhost/dev",
                    "API_TOKEN=invalid-token",
                    "EXTRA=value",
                    "API_TOKEN=override",
                ],
            ),
            encoding="utf-8",
        )
        result = runner.invoke(app, ["check", str(env_file), "--spec", str(EXAMPLE_SPEC)])
        assert result.exit_code == 1
        table_lines = [line for line in result.stdout.splitlines() if line.startswith("│")]
        error_index = next(i for i, line in enumerate(table_lines) if "ERROR" in line)
        warning_index = next(i for i, line in enumerate(table_lines) if "WARNING" in line)
        assert error_index < warning_index
        assert "Errors: 1" in result.stdout
        assert "Warnings: 1" in result.stdout
        assert "Impacted:" in result.stdout
        assert "Info" not in result.stdout


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
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["report"]
    assert payload["summary"]
    assert payload["summary"]["by_kind"]["changed"] == 4
    assert payload["summary"]["non_empty_kinds"] == ["changed"]
    assert payload["summary"]["variables"] == [
        "ALLOWED_HOSTS",
        "API_TOKEN",
        "DATABASE_URL",
        "DEBUG",
    ]
    assert payload["summary"]["top_variables"][0][0] == "ALLOWED_HOSTS"
    report_payload = payload["report"]
    assert report_payload["is_clean"] is False
    assert report_payload["by_kind"]["missing"] == 0
    assert report_payload["variables"] == ["ALLOWED_HOSTS", "API_TOKEN", "DATABASE_URL", "DEBUG"]
    assert report_payload["top_variables"][0][0] == "ALLOWED_HOSTS"
