from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from .report import DiffReport, IssueSeverity, ValidationReport
from .snapshot import EnvSnapshot
from .spec import EnvSpec

app = typer.Typer(help="Deterministic environment spec and drift detection for .env workflows.")
console = Console()


def load_spec(path: Path) -> EnvSpec:
    try:
        return EnvSpec.from_file(path)
    except FileNotFoundError as exc:  # pragma: no cover - Typer handles message but keep guard
        raise typer.BadParameter(f"spec file not found: {path}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise typer.BadParameter(f"failed to load spec: {exc}") from exc


@app.command()
def check(
    env_file: Annotated[Path, typer.Argument(help="Path to the environment file.")],
    spec: Annotated[Path, typer.Option("--spec", "-s", help="Path to envkeep spec.")] = Path("envkeep.toml"),
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", case_sensitive=False, help="Output format: text or json."),
    ] = "text",
    allow_extra: Annotated[bool, typer.Option(help="Allow variables not declared in the spec.")] = False,
    fail_on_warnings: Annotated[
        bool,
        typer.Option(
            "--fail-on-warnings/--no-fail-on-warnings",
            help="Treat warnings as errors for CI enforcement.",
        ),
    ] = False,
) -> None:
    """Validate an environment against the specification."""

    env_spec = load_spec(spec)
    if str(env_file) == "-":
        data = sys.stdin.read()
        snapshot = EnvSnapshot.from_text(data, source="stdin")
    else:
        snapshot = EnvSnapshot.from_env_file(env_file)
    report = env_spec.validate(snapshot, allow_extra=allow_extra)
    if output_format.lower() == "json":
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        render_validation_report(report, source=str(env_file))
    exit_code = 0
    if not report.is_success or (fail_on_warnings and report.warning_count > 0):
        exit_code = 1
    raise typer.Exit(code=exit_code)


@app.command()
def diff(
    first: Annotated[Path, typer.Argument(help="Baseline environment file.")],
    second: Annotated[Path, typer.Argument(help="Target environment file.")],
    spec: Annotated[Path, typer.Option("--spec", "-s", help="Path to envkeep spec.")] = Path("envkeep.toml"),
    output_format: Annotated[
        str, typer.Option("--format", "-f", case_sensitive=False, help="Output format: text or json.")
    ] = "text",
) -> None:
    """Compare two environment files using the spec for normalization."""

    env_spec = load_spec(spec)
    stdin_buffer: str | None = None
    minus_count = sum(1 for candidate in (str(first), str(second)) if candidate == "-")
    if minus_count > 1:
        raise typer.BadParameter("stdin can only be supplied for one file in diff.")

    def load_snapshot(path: Path, *, label: str) -> EnvSnapshot:
        nonlocal stdin_buffer
        if str(path) == "-":
            if stdin_buffer is None:
                stdin_buffer = sys.stdin.read()
            return EnvSnapshot.from_text(stdin_buffer, source=f"stdin:{label}")
        return EnvSnapshot.from_env_file(path)

    left = load_snapshot(first, label="left")
    right = load_snapshot(second, label="right")
    report = env_spec.diff(left, right)
    if output_format.lower() == "json":
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        render_diff_report(report, left=str(first), right=str(second))
    raise typer.Exit(code=0 if report.is_clean() else 1)


@app.command()
def generate(
    spec: Annotated[Path, typer.Option("--spec", "-s", help="Path to envkeep spec.")] = Path("envkeep.toml"),
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Where to write the generated file.")] = None,
    redact_secrets: Annotated[bool, typer.Option(help="Mask variables marked as secret.")] = True,
) -> None:
    """Generate a sanitized .env example from the spec."""

    env_spec = load_spec(spec)
    content = env_spec.generate_example(redact_secrets=redact_secrets)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote example to {output}")
    else:
        typer.echo(content)


@app.command()
def inspect(
    spec: Annotated[Path, typer.Option("--spec", "-s", help="Path to envkeep spec.")] = Path("envkeep.toml")
) -> None:
    """Print a summary of variables and profiles declared in the spec."""

    env_spec = load_spec(spec)
    table = Table(title=f"Envkeep Summary (version {env_spec.version})")
    table.add_column("Variable")
    table.add_column("Type")
    table.add_column("Required")
    table.add_column("Secret")
    table.add_column("Description")
    for variable in env_spec.variables:
        table.add_row(
            variable.name,
            variable.var_type.value,
            "yes" if variable.required else "no",
            "yes" if variable.secret else "no",
            variable.description or "",
        )
    if env_spec.profiles:
        table.add_section()
        table.add_row("Profiles", "", "", "", "")
        for profile in env_spec.profiles:
            table.add_row(
                f"• {profile.name}",
                "",
                "",
                "",
                profile.description or profile.env_file,
            )
    console.print(table)


@app.command()
def doctor(
    spec: Annotated[Path, typer.Option("--spec", "-s", help="Path to envkeep spec.")] = Path("envkeep.toml"),
    profile: Annotated[
        str,
        typer.Option("--profile", "-p", help="Profile to validate (all to run every profile).", show_default=True),
    ] = "all",
    allow_extra: Annotated[bool, typer.Option(help="Allow extra variables when validating profiles.")] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", case_sensitive=False, help="Output format: text or json."),
    ] = "text",
    fail_on_warnings: Annotated[
        bool,
        typer.Option(
            "--fail-on-warnings/--no-fail-on-warnings",
            help="Fail when any profile emits warnings.",
        ),
    ] = False,
) -> None:
    """Validate one or more profiles declared in the spec."""

    env_spec = load_spec(spec)
    profiles = list(env_spec.iter_profiles())
    if not profiles:
        typer.echo("No profiles declared in spec.")
        raise typer.Exit(code=0)

    selected: list[tuple[str, Path]] = []
    if profile == "all":
        selected = [(item.name, Path(item.env_file)) for item in profiles]
    else:
        mapping = env_spec.profiles_by_name()
        if profile not in mapping:
            raise typer.BadParameter(f"profile '{profile}' not found")
        item = mapping[profile]
        selected = [(item.name, Path(item.env_file))]

    exit_code = 0
    output_mode = output_format.lower()
    results: list[dict[str, Any]] = []
    for name, env_path in selected:
        if not env_path.exists():
            if output_mode == "json":
                results.append({
                    "profile": name,
                    "path": str(env_path),
                    "error": "missing env file",
                })
            else:
                typer.echo(f"Profile {name}: missing env file {env_path}")
            exit_code = 1
            continue
        snapshot = EnvSnapshot.from_env_file(env_path)
        report = env_spec.validate(snapshot, allow_extra=allow_extra)
        if output_mode == "json":
            results.append({
                "profile": name,
                "path": str(env_path),
                "report": report.to_dict(),
                "warnings": _summarize_warnings(report),
            })
        else:
            console.rule(f"Profile: {name}")
            render_validation_report(report, source=str(env_path))
        if not report.is_success or (fail_on_warnings and report.warning_count > 0):
            exit_code = 1
    if output_mode == "json":
        payload = {
            "profiles": results,
            "allow_extra": allow_extra,
            "fail_on_warnings": fail_on_warnings,
        }
        typer.echo(json.dumps(payload, indent=2))
    raise typer.Exit(code=exit_code)


def _summarize_warnings(report: ValidationReport) -> dict[str, Any]:
    duplicates = [issue.variable for issue in report.issues if issue.code == "duplicate"]
    extras = [issue.variable for issue in report.issues if issue.code == "extra"]
    invalid_lines = [
        {"line": issue.variable, "hint": issue.hint or issue.message}
        for issue in report.issues
        if issue.code == "invalid_line"
    ]
    return {
        "total": report.warning_count,
        "duplicates": duplicates,
        "extra_variables": extras,
        "invalid_lines": invalid_lines,
    }


def render_validation_report(report: ValidationReport, *, source: str) -> None:
    console.print(f"Validating [bold]{source}[/bold]")
    if not report.issues:
        console.print("[green]All checks passed.[/green]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Severity")
    table.add_column("Variable")
    table.add_column("Code")
    table.add_column("Message")
    table.add_column("Hint", overflow="fold")
    for issue in report.issues:
        style = {
            IssueSeverity.ERROR: "red",
            IssueSeverity.WARNING: "yellow",
            IssueSeverity.INFO: "blue",
        }[issue.severity]
        table.add_row(
            f"[{style}]{issue.severity.value.upper()}[/{style}]",
            issue.variable,
            issue.code,
            issue.message,
            issue.hint or "",
        )
    console.print(table)
    console.print(f"Errors: {report.error_count} · Warnings: {report.warning_count}")


def render_diff_report(report: DiffReport, *, left: str, right: str) -> None:
    console.print(f"Diffing [bold]{left}[/bold] -> [bold]{right}[/bold]")
    if report.is_clean():
        console.print("[green]No drift detected.[/green]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Variable")
    table.add_column("Change")
    table.add_column("Left")
    table.add_column("Right")
    for entry in report.entries:
        table.add_row(
            entry.variable,
            entry.kind.value,
            entry.redacted_left() or "",
            entry.redacted_right() or "",
        )
    console.print(table)
    console.print(f"Total differences: {report.change_count}")


if __name__ == "__main__":
    app()
