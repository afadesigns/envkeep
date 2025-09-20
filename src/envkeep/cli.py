from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import warnings

import typer
from rich.console import Console
from rich.table import Table

from .report import DiffKind, DiffReport, IssueSeverity, ValidationIssue, ValidationReport
from .snapshot import EnvSnapshot
from .spec import EnvSpec
from ._compat import tomllib

try:  # pragma: no cover - Click 8.0 compatibility
    from click._utils import UNSET as _CLICK_UNSET
except ImportError:  # pragma: no cover - Click >=8.1 renamed internals
    _CLICK_UNSET = None

if _CLICK_UNSET is None:  # pragma: no cover - Typer >=0.12 on newer Click versions
    warnings.filterwarnings(
        "ignore",
        message="The 'is_flag' and 'flag_value' parameters are not supported by Typer",
        category=DeprecationWarning,
    )

app = typer.Typer(help="Deterministic environment spec and drift detection for .env workflows.")
console = Console()

class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


def _parse_output_format(value: OutputFormat | str) -> OutputFormat:
    if isinstance(value, OutputFormat):
        return value
    try:
        return OutputFormat(str(value).lower())
    except ValueError as exc:
        allowed = ", ".join(fmt.value for fmt in OutputFormat)
        raise typer.BadParameter(
            f"Invalid value for '--format': output format must be one of: {allowed}"
        ) from exc


def _option_with_value(*args: Any, **kwargs: Any) -> typer.models.OptionInfo:
    option = typer.Option(*args, **kwargs)
    if _CLICK_UNSET is not None:
        option.flag_value = _CLICK_UNSET  # Click <8.1 treats flag_value=None as a boolean flag
    return option


def _coerce_output_format(raw: str) -> OutputFormat:
    try:
        return _parse_output_format(raw)
    except typer.BadParameter as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc


def _format_option() -> typer.models.OptionInfo:
    option = _option_with_value(
        "text",
        "--format",
        "-f",
        help="Output format: text or json.",
    )
    option.case_sensitive = False
    return option


def _spec_option() -> typer.models.OptionInfo:
    return _option_with_value(Path("envkeep.toml"), "--spec", "-s", help="Path to envkeep spec.")


def _profile_option() -> typer.models.OptionInfo:
    option = _option_with_value(
        "all",
        "--profile",
        "-p",
        help="Profile to validate (all to run every profile).",
    )
    option.show_default = True
    return option


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _casefold_sorted(values: Iterable[str]) -> list[str]:
    return sorted(values, key=lambda name: (name.casefold(), name))


def _sorted_counter(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _normalized_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    return max(limit, 0)


def _usage_error(message: str) -> None:
    """Emit a usage error to stderr and exit with the conventional code."""

    typer.echo(message, err=True)
    raise typer.Exit(code=2)


def _handle_validation_output(
    report: ValidationReport,
    *,
    source: str,
    output_format: OutputFormat,
    fail_on_warnings: bool,
    summary_top: int | None,
) -> int:
    limit = _normalized_limit(summary_top)
    if output_format is OutputFormat.JSON:
        payload = {
            "report": report.to_dict(top_limit=limit),
            "summary": report.summary(top_limit=limit),
        }
        _emit_json(payload)
    else:
        render_validation_report(report, source=source, top_limit=limit)
    exit_code = 0
    if report.has_errors or (fail_on_warnings and report.has_warnings):
        exit_code = 1
    return exit_code


def _handle_diff_output(
    report: DiffReport,
    *,
    left: str,
    right: str,
    output_format: OutputFormat,
    summary_top: int | None,
) -> int:
    limit = _normalized_limit(summary_top)
    if output_format is OutputFormat.JSON:
        payload = {
            "report": report.to_dict(top_limit=limit),
            "summary": report.summary(top_limit=limit),
        }
        _emit_json(payload)
    else:
        render_diff_report(report, left=left, right=right, top_limit=limit)
    return 0 if report.is_clean() else 1


def _format_severity_summary(report: ValidationReport, *, top_limit: int | None) -> str:
    limit = _normalized_limit(top_limit)
    totals = report.severity_totals()
    ordered = [
        ("Errors", IssueSeverity.ERROR.value),
        ("Warnings", IssueSeverity.WARNING.value),
        ("Info", IssueSeverity.INFO.value),
    ]
    parts = [
        f"{label}: {totals[key]}"
        for label, key in ordered
        if totals[key] > 0
    ]
    if not parts:
        parts = [f"{label}: {totals[key]}" for label, key in ordered]
    if limit is None:
        top_variables = [name for name, _ in report.top_variables()]
    elif limit == 0:
        top_variables = []
    else:
        top_variables = [name for name, _ in report.top_variables(limit)]
    if top_variables:
        parts.append("Impacted: " + ", ".join(top_variables))
    return " · ".join(parts)


def _format_diff_summary(report: DiffReport, *, top_limit: int | None) -> str:
    limit = _normalized_limit(top_limit)
    summary = report.counts_by_kind()
    ordered = [
        ("Missing", DiffKind.MISSING.value),
        ("Extra", DiffKind.EXTRA.value),
        ("Changed", DiffKind.CHANGED.value),
    ]
    parts = [
        f"{label}: {summary[key]}"
        for label, key in ordered
        if summary[key] > 0
    ]
    if not parts:
        parts = [f"{label}: {summary[key]}" for label, key in ordered]
    if limit is None:
        top_variables = [name for name, _ in report.top_variables()]
    elif limit == 0:
        top_variables = []
    else:
        top_variables = [name for name, _ in report.top_variables(limit)]
    if top_variables:
        parts.append("Impacted: " + ", ".join(top_variables))
    return " · ".join(parts)


def _emit_doctor_json(
    results: list[dict[str, Any]],
    *,
    allow_extra: bool,
    fail_on_warnings: bool,
    top_limit: int,
    aggregated_codes: list[tuple[str, int]],
    aggregated_top_variables: list[tuple[str, int]],
    aggregated_variables: list[str],
) -> None:
    severity_totals = {
        IssueSeverity.ERROR.value: 0,
        IssueSeverity.WARNING.value: 0,
        IssueSeverity.INFO.value: 0,
    }
    successes = 0
    missing_profiles = sum(1 for item in results if "error" in item)
    aggregated_duplicates: set[str] = set()
    aggregated_extras: set[str] = set()
    aggregated_invalid_lines: list[dict[str, Any]] = []
    for item in results:
        summary = item.get("summary")
        if not summary:
            continue
        successes += 1
        for key, value in summary["severity_totals"].items():
            severity_totals[key] += value
        warnings = item.get("warnings")
        if warnings:
            aggregated_duplicates.update(warnings.get("duplicates", ()))
            aggregated_extras.update(warnings.get("extra_variables", ()))
            profile = item.get("profile")
            for warning in warnings.get("invalid_lines", ()):  # already copy-on-read
                if profile is None:
                    aggregated_invalid_lines.append(warning)
                else:
                    aggregated_invalid_lines.append({**warning, "profile": profile})
    non_empty_severities = [
        key
        for key, value in severity_totals.items()
        if value > 0
    ]
    if not non_empty_severities:
        non_empty_severities = list(severity_totals.keys())
    summary_payload = {
        "profiles_with_reports": successes,
        "missing_profiles": missing_profiles,
        "severity_totals": severity_totals,
        "is_success": successes > 0
        and all(item["summary"]["is_success"] for item in results if "summary" in item)
        and all("error" not in item for item in results),
        "non_empty_severities": non_empty_severities,
        "most_common_codes": aggregated_codes,
        "variables": aggregated_variables,
        "top_variables": aggregated_top_variables,
    }
    def _line_number(entry: dict[str, Any]) -> int:
        raw = entry.get("line", "")
        digits = "".join(char for char in raw if char.isdigit())
        return int(digits) if digits else 0

    warnings_payload = {
        "duplicates": _casefold_sorted(aggregated_duplicates),
        "extra_variables": _casefold_sorted(aggregated_extras),
        "invalid_lines": sorted(
            aggregated_invalid_lines,
            key=lambda item: (
                item.get("profile", ""),
                _line_number(item),
                item.get("line", ""),
            ),
        ),
    }
    payload = {
        "profiles": results,
        "allow_extra": allow_extra,
        "fail_on_warnings": fail_on_warnings,
        "summary": summary_payload,
        "warnings": warnings_payload,
    }
    _emit_json(payload)


def load_spec(path: Path, *, stdin_data: str | None = None) -> EnvSpec:
    path_str = str(path)
    try:
        if path_str == "-":
            content = stdin_data if stdin_data is not None else sys.stdin.read()
            if not content.strip():
                raise typer.BadParameter("spec input from stdin is empty")
            data = tomllib.loads(content)
            return EnvSpec.from_dict(data)
        return EnvSpec.from_file(path)
    except FileNotFoundError as exc:  # pragma: no cover - Typer handles message but keep guard
        raise typer.BadParameter(f"spec file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - exercised via CLI tests
        detail = getattr(exc, "msg", str(exc))
        line = getattr(exc, "lineno", None)
        col = getattr(exc, "colno", None)
        if line is not None and col is not None:
            detail = f"{detail} (line {line}, column {col})"
        message = f"failed to parse spec: {detail}"
        typer.echo(message)
        raise typer.BadParameter(message) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise typer.BadParameter(f"failed to load spec: {exc}") from exc


@app.command()
def check(
    env_file: Path = typer.Argument(..., help="Path to the environment file."),
    spec: Path = _spec_option(),
    output_format: str = _format_option(),
    allow_extra: bool = typer.Option(
        False,
        "--allow-extra",
        help="Allow variables not declared in the spec.",
        is_flag=True,
        flag_value=True,
    ),
    fail_on_warnings: bool = typer.Option(
        False,
        "--fail-on-warnings",
        help="Treat warnings as errors for CI enforcement.",
        is_flag=True,
        flag_value=True,
    ),
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables/codes shown in summaries (0 to suppress).",
    ),
) -> None:
    """Validate an environment against the specification."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")
    env_path = str(env_file)
    spec_path = str(spec)
    if spec_path == "-" and env_path == "-":
        _usage_error("cannot read both spec and environment from stdin")
    stdin_spec: str | None = None
    if spec_path == "-":
        stdin_spec = sys.stdin.read()
    env_spec = load_spec(spec, stdin_data=stdin_spec)
    if env_path == "-":
        data = sys.stdin.read()
        snapshot = EnvSnapshot.from_text(data, source="stdin")
    else:
        snapshot = EnvSnapshot.from_env_file(env_file)
    report = env_spec.validate(snapshot, allow_extra=allow_extra)
    fmt = _coerce_output_format(output_format)
    exit_code = _handle_validation_output(
        report,
        source=str(env_file),
        output_format=fmt,
        fail_on_warnings=fail_on_warnings,
        summary_top=summary_top,
    )
    raise typer.Exit(code=exit_code)


@app.command()
def diff(
    first: Path = typer.Argument(..., help="Baseline environment file."),
    second: Path = typer.Argument(..., help="Target environment file."),
    spec: Path = _spec_option(),
    output_format: str = _format_option(),
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables shown in summaries (0 to suppress).",
    ),
) -> None:
    """Compare two environment files using the spec for normalization."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")
    spec_path = str(spec)
    minus_count = sum(1 for candidate in (str(first), str(second)) if candidate == "-")
    if spec_path == "-" and minus_count:
        _usage_error("cannot combine spec from stdin with environment stdin input")
    stdin_spec: str | None = None
    if spec_path == "-":
        stdin_spec = sys.stdin.read()
    env_spec = load_spec(spec, stdin_data=stdin_spec)
    stdin_buffer: str | None = None
    if minus_count > 1:
        _usage_error("stdin can only be supplied for one file in diff.")

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
    fmt = _coerce_output_format(output_format)
    exit_code = _handle_diff_output(
        report,
        left=str(first),
        right=str(second),
        output_format=fmt,
        summary_top=summary_top,
    )
    raise typer.Exit(code=exit_code)


@app.command()
def generate(
    spec: Path = _spec_option(),
    output: Optional[Path] = _option_with_value(
        None,
        "--output",
        "-o",
        help="Where to write the generated file.",
    ),
    no_redact_secrets: bool = typer.Option(
        False,
        "--no-redact-secrets",
        help="Disable masking for variables marked as secret.",
        is_flag=True,
        flag_value=True,
    ),
) -> None:
    """Generate a sanitized .env example from the spec."""

    env_spec = load_spec(spec)
    content = env_spec.generate_example(redact_secrets=not no_redact_secrets)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote example to {output}")
    else:
        typer.echo(content)


@app.command()
def inspect(
    spec: Path = _spec_option(),
    output_format: str = _format_option(),
) -> None:
    """Print a summary of variables and profiles declared in the spec."""

    env_spec = load_spec(spec)
    fmt = _coerce_output_format(output_format)
    if fmt is OutputFormat.JSON:
        variables_payload = [
            {
                "name": variable.name,
                "type": variable.var_type.value,
                "required": variable.required,
                "secret": variable.secret,
                "description": variable.description,
                "default": variable.default,
                "choices": list(variable.choices),
                "pattern": variable.pattern.pattern if variable.pattern else None,
                "example": variable.example,
                "allow_empty": variable.allow_empty,
            }
            for variable in env_spec.variables
        ]
        profiles_payload = [
            {
                "name": profile.name,
                "env_file": profile.env_file,
                "description": profile.description,
            }
            for profile in env_spec.profiles
        ]
        payload = {
            "summary": env_spec.summary(),
            "variables": variables_payload,
            "profiles": profiles_payload,
        }
        _emit_json(payload)
        return
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
    spec: Path = _spec_option(),
    profile: str = _profile_option(),
    allow_extra: bool = typer.Option(
        False,
        "--allow-extra",
        help="Allow extra variables when validating profiles.",
        is_flag=True,
        flag_value=True,
    ),
    output_format: str = _format_option(),
    fail_on_warnings: bool = typer.Option(
        False,
        "--fail-on-warnings",
        help="Fail when any profile emits warnings.",
        is_flag=True,
        flag_value=True,
    ),
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables/codes shown in summaries (0 to suppress).",
    ),
) -> None:
    """Validate one or more profiles declared in the spec."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")
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
    fmt = _coerce_output_format(output_format)
    use_json = fmt is OutputFormat.JSON
    results: list[dict[str, Any]] = []
    total_errors = 0
    total_warnings = 0
    total_info = 0
    missing_profiles = 0
    checked_profiles = 0
    aggregate_warning_counts = {
        "duplicates": 0,
        "extra_variables": 0,
        "invalid_lines": 0,
    }
    aggregate_issue_variables: set[str] = set()
    aggregated_codes: Counter[str] = Counter()
    aggregated_variables: set[str] = set()
    aggregated_variable_counts: Counter[str] = Counter()
    top_limit = _normalized_limit(summary_top) or 0
    for name, env_path in selected:
        if not env_path.exists():
            missing_profiles += 1
            if use_json:
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
        checked_profiles += 1
        severity_totals = report.severity_totals()
        total_errors += severity_totals[IssueSeverity.ERROR.value]
        total_warnings += severity_totals[IssueSeverity.WARNING.value]
        total_info += severity_totals[IssueSeverity.INFO.value]
        warnings_summary = report.warning_summary()
        aggregate_warning_counts["duplicates"] += len(warnings_summary["duplicates"])
        aggregate_warning_counts["extra_variables"] += len(warnings_summary["extra_variables"])
        aggregate_warning_counts["invalid_lines"] += len(warnings_summary["invalid_lines"])
        full_summary = report.summary()
        aggregate_issue_variables.update(full_summary.get("variables", []))
        aggregated_codes.update(full_summary.get("codes", {}))
        aggregated_variables.update(full_summary.get("variables", ()))
        for variable, count in full_summary.get("top_variables", []):
            aggregated_variable_counts[variable] += count
        if use_json:
            summary = report.summary(top_limit=top_limit)
            report_payload = report.to_dict(top_limit=top_limit)
            results.append({
                "profile": name,
                "path": str(env_path),
                "report": report_payload,
                "summary": summary,
                "warnings": warnings_summary,
            })
        else:
            console.rule(f"Profile: {name}")
            render_validation_report(report, source=str(env_path), top_limit=top_limit)
        if report.has_errors or (fail_on_warnings and report.has_warnings):
            exit_code = 1
    aggregated_most_common_codes = _sorted_counter(aggregated_codes)
    aggregated_variables_list = _casefold_sorted(aggregated_variables)
    aggregated_top_variables = _sorted_counter(aggregated_variable_counts)
    if top_limit == 0:
        aggregated_most_common_codes = []
        aggregated_top_variables = []
    else:
        aggregated_most_common_codes = aggregated_most_common_codes[:top_limit]
        aggregated_top_variables = aggregated_top_variables[:top_limit]
    if use_json:
        _emit_doctor_json(
            results,
            allow_extra=allow_extra,
            fail_on_warnings=fail_on_warnings,
            top_limit=top_limit,
            aggregated_codes=aggregated_most_common_codes,
            aggregated_top_variables=aggregated_top_variables,
            aggregated_variables=aggregated_variables_list,
        )
    else:
        console.rule("Doctor Summary")
        console.print(
            f"Profiles checked: {checked_profiles}/{len(selected)}"
        )
        console.print(
            " · ".join(
                [
                    f"Missing profiles: {missing_profiles}",
                    f"Total errors: {total_errors}",
                    f"Total warnings: {total_warnings}",
                    f"Total info: {total_info}",
                ]
            )
        )
        console.print(
            "Warnings breakdown: "
            f"Duplicates: {aggregate_warning_counts['duplicates']} · "
            f"Extra variables: {aggregate_warning_counts['extra_variables']} · "
            f"Invalid lines: {aggregate_warning_counts['invalid_lines']}"
        )
        if aggregate_issue_variables and top_limit != 0:
            sorted_variables = _casefold_sorted(aggregate_issue_variables)
            display_count = min(len(sorted_variables), top_limit)
            console.print(
                "Impacted variables: "
                + ", ".join(sorted_variables[:display_count])
            )
        if aggregated_most_common_codes:
            formatted_codes = ", ".join(
                f"{code}({count})"
                for code, count in aggregated_most_common_codes
            )
            console.print(f"Top issue codes: {formatted_codes}")
        if aggregated_top_variables and top_limit != 0:
            formatted_variables = ", ".join(
                f"{variable}({count})"
                for variable, count in aggregated_top_variables
            )
            console.print(f"Top impacted variables: {formatted_variables}")
    raise typer.Exit(code=exit_code)

def render_validation_report(
    report: ValidationReport,
    *,
    source: str,
    top_limit: int | None = None,
) -> None:
    console.print(f"Validating [bold]{source}[/bold]")
    if not report.issues:
        console.print("[green]All checks passed.[/green]")
        return
    style_map = {
        IssueSeverity.ERROR: "red",
        IssueSeverity.WARNING: "yellow",
        IssueSeverity.INFO: "blue",
    }
    label_map = {
        IssueSeverity.ERROR: "Errors",
        IssueSeverity.WARNING: "Warnings",
        IssueSeverity.INFO: "Info",
    }
    first_section = True
    for severity in report.non_empty_severities():
        issues = report.issues_by_severity(severity)
        if not first_section:
            console.print()
        first_section = False
        console.print(f"[bold underline]{label_map[severity]}[/]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity")
        table.add_column("Variable")
        table.add_column("Code")
        table.add_column("Message")
        table.add_column("Hint", overflow="fold")
        style = style_map[severity]
        for issue in issues:
            table.add_row(
                f"[{style}]{severity.value.upper()}[/{style}]",
                issue.variable,
                issue.code,
                issue.message,
                issue.hint or "",
            )
        console.print(table)
    console.print(_format_severity_summary(report, top_limit=top_limit))


def render_diff_report(
    report: DiffReport,
    *,
    left: str,
    right: str,
    top_limit: int | None = None,
) -> None:
    console.print(f"Diffing [bold]{left}[/bold] -> [bold]{right}[/bold]")
    if report.is_clean():
        console.print("[green]No drift detected.[/green]")
        return
    style_map = {
        DiffKind.MISSING: "yellow",
        DiffKind.EXTRA: "blue",
        DiffKind.CHANGED: "red",
    }
    label_map = {
        DiffKind.MISSING: "Missing",
        DiffKind.EXTRA: "Extra",
        DiffKind.CHANGED: "Changed",
    }
    first_section = True
    for kind in report.non_empty_kinds():
        entries = report.entries_by_kind(kind)
        if not first_section:
            console.print()
        first_section = False
        console.print(f"[bold underline]{label_map[kind]}[/]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Variable")
        table.add_column("Change")
        table.add_column("Left")
        table.add_column("Right")
        style = style_map[kind]
        for entry in entries:
            table.add_row(
                entry.variable,
                f"[{style}]{entry.kind.value.upper()}[/{style}]",
                entry.redacted_left() or "",
                entry.redacted_right() or "",
            )
        console.print(table)
    console.print(_format_diff_summary(report, top_limit=top_limit))
    console.print(f"Total differences: {report.change_count}")


if __name__ == "__main__":
    app()
