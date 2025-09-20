from __future__ import annotations

import json
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
PROD_ENV_ABS = PROD_ENV.resolve()
def test_cli_check_success() -> None:
    result = runner.invoke(app, ["check", str(DEV_ENV), "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 0
    assert "All checks passed" in result.stdout


def test_cli_check_failure(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=http://example.com\n", encoding="utf-8")
    result = runner.invoke(app, ["check", str(env_file), "--spec", str(EXAMPLE_SPEC)])
    assert result.exit_code == 1
    assert 'API_TOKEN' in result.stdout
    assert 'Errors: 1' in result.stdout


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
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
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
    assert result.exit_code != 0
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
            ]
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
            ]
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, [
        "diff",
        str(left),
        str(right),
        "--spec",
        str(EXAMPLE_SPEC),
    ])
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


def test_cli_doctor_resolves_relative_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_dir = tmp_path / "spec"
    env_dir = tmp_path / "env"
    home_dir = tmp_path / "home"
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
            """
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", "--spec", str(spec_file)])
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
        spec_text
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(missing)),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["doctor", "--spec", str(spec_copy)])
    assert result.exit_code == 1
    assert "missing env file" in result.stdout


def test_cli_doctor_json_output(tmp_path: Path) -> None:
    env_file = tmp_path / "dev.env"
    env_file.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(env_file))
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
            ]
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(PROD_ENV_ABS))
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
            ]
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(PROD_ENV_ABS))
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


def test_cli_doctor_json_summary_top_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
            ]
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(PROD_ENV_ABS))
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
            ]
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
    assert summary["issue_count"] == summary["severity_totals"]["error"] + summary["severity_totals"]["warning"] + summary["severity_totals"]["info"]
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


def test_cli_check_summary_top_zero_suppresses_impacted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ]
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


def test_cli_check_json_respects_summary_top(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ]
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
            ]
        ),
        encoding="utf-8",
    )
    spec_text = (
        EXAMPLE_SPEC.read_text()
        .replace("examples/basic/.env.dev", str(env_file))
        .replace("examples/basic/.env.prod", str(PROD_ENV_ABS))
    )
    spec_copy = tmp_path / "envkeep.toml"
    spec_copy.write_text(spec_text, encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--spec", str(spec_copy)])
    assert result.exit_code == 0
    assert "Impacted variables:" in result.stdout
    assert "Top impacted variables:" in result.stdout


def test_cli_doctor_reports_summary(tmp_path: Path) -> None:
    dev_env = tmp_path / "dev.env"
    dev_env.write_text(DEV_ENV.read_text(), encoding="utf-8")
    spec_text = (
        EXAMPLE_SPEC.read_text(encoding="utf-8")
        .replace("examples/basic/.env.dev", str(dev_env))
        .replace("examples/basic/.env.prod", str(tmp_path / "missing.env"))
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
    assert "Warnings breakdown: Duplicates: 0 · Extra variables: 0 · Invalid lines: 0" in result.stdout
    assert "Impacted variables:" not in result.stdout


def test_cli_check_reads_from_stdin() -> None:
    stdin_content = "\n".join(
        [
            "DATABASE_URL=postgresql://localhost/dev",
            "DEBUG=false",
            "ALLOWED_HOSTS=localhost",
            "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
        ]
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


def test_cli_diff_summary_top_zero_omits_impacted(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
            ]
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
            ]
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
    assert "Changed: 1" in result.stdout
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


def test_cli_inspect_json_output() -> None:
    result = runner.invoke(
        app,
        [
            "inspect",
            "--spec",
            str(EXAMPLE_SPEC),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["version"] == 1
    first_variable = payload["variables"][0]
    assert first_variable["name"] == "DATABASE_URL"
    assert "profiles" in payload


def test_cli_check_orders_severity_and_reports_info(tmp_path: Path) -> None:
    env_file = tmp_path / "bad.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "API_TOKEN=invalid-token",
                "EXTRA=value",
                "API_TOKEN=override",
            ]
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
    assert "Warnings: 2" in result.stdout
    assert "Impacted:" in result.stdout
    assert "Info" not in result.stdout
