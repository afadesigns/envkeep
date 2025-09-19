from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from envkeep.cli import app

runner = CliRunner()
EXAMPLE_SPEC = Path("examples/basic/envkeep.toml")
DEV_ENV = Path("examples/basic/.env.dev")
PROD_ENV = Path("examples/basic/.env.prod")


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
    assert payload["profiles"][0]["report"]["is_success"] is True
    assert payload["profiles"][0]["warnings"]["total"] == 0


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
    spec_text = EXAMPLE_SPEC.read_text().replace("examples/basic/.env.dev", str(env_file))
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


def test_cli_doctor_json_warnings(tmp_path: Path) -> None:
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
    spec_text = EXAMPLE_SPEC.read_text().replace("examples/basic/.env.dev", str(env_file))
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
    warnings = payload["profiles"][0]["warnings"]
    assert warnings["total"] == 1
    assert warnings["extra_variables"] == ["EXTRA"]


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
