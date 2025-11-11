from __future__ import annotations

import json
import logging
import sys
import warnings
from collections import Counter, defaultdict
from enum import Enum
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console
from rich.table import Table

from ._compat import tomllib
from .cache import Cache
from .config import load_config
from .plugins import load_backends
from .report import DiffKind, DiffReport, IssueSeverity, ValidationReport
from .snapshot import EnvSnapshot
from .spec import EnvSpec, ProfileSpec
from .utils import (
    OptionalPath,
    casefold_sorted,
    find_spec_path,
    line_number_sort_key,
    normalized_limit,
    resolve_optional_path_option,
    sorted_counter,
)

from importlib import metadata

__version__ = metadata.version("envkeep")

logger = logging.getLogger(__name__)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"envkeep version: {__version__}")
        raise typer.Exit()


try:  # pragma: no cover - Click 8.0 compatibility
    from click._utils import UNSET as _CLICK_UNSET  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Click >=8.1 renamed internals
    _CLICK_UNSET = None

if _CLICK_UNSET is None:  # pragma: no cover - Typer >=0.12 on newer Click versions
    warnings.filterwarnings(
        "ignore",
        message="The 'is_flag' and 'flag_value' parameters are not supported by Typer",
        category=DeprecationWarning,
    )

app = typer.Typer(
    help="Deterministic environment spec and drift detection for .env workflows.",
    add_completion=True,
)
console = Console()
DEFAULT_OUTPUT_FORMAT = "text"
DEFAULT_PROFILE = "all"


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Callback to configure the main application context."""
    pass


def _fetch_remote_values(spec: EnvSpec) -> dict[str, str]:
    """Fetch values from all remote backends defined in the spec."""
    backends = load_backends()
    if not backends:
        return {}

    sources_by_backend: dict[str, dict[str, str]] = defaultdict(dict)
    for var in spec.variables:
        if var.source:
            try:
                backend_name, source_uri = var.source.split(":", 1)
                if backend_name in backends:
                    sources_by_backend[backend_name][var.name] = source_uri
            except ValueError:
                # Ignore malformed source strings
                pass

    fetched_values: dict[str, str] = {}
    for backend_name, sources in sources_by_backend.items():
        backend = backends[backend_name]
        try:
            results = backend.fetch(sources)
            fetched_values.update(results)
        except Exception:
            logger.exception("Plugin %s failed to fetch secrets", backend_name)

    return fetched_values


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
            f"Invalid value for '--format': output format must be one of: {allowed}",
        ) from exc


def _option_with_value(*args: Any, **kwargs: Any) -> typer.models.OptionInfo:
    option = cast(typer.models.OptionInfo, typer.Option(*args, **kwargs))
    if option.param_decls:
        option.param_decls = tuple(decl for decl in option.param_decls if isinstance(decl, str))
    else:
        option.param_decls = ()
    if _CLICK_UNSET is not None and hasattr(option, "flag_value"):
        option.flag_value = _CLICK_UNSET  # Click <8.1 treats flag_value=None as a boolean flag
    return option


def _coerce_output_format(raw: str) -> OutputFormat:
    try:
        return _parse_output_format(raw)
    except typer.BadParameter as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc


SPEC_OPTION = _option_with_value(
    None,
    "--spec",
    "-s",
    help="Path to envkeep spec (searches parents if not specified).",
)
FORMAT_OPTION = _option_with_value(
    DEFAULT_OUTPUT_FORMAT,
    "--format",
    "-f",
    help="Output format: text or json.",
)
FORMAT_OPTION.case_sensitive = False
PROFILE_OPTION = _option_with_value(
    DEFAULT_PROFILE,
    "--profile",
    "-p",
    help="Profile to validate (all to run every profile).",
)
PROFILE_OPTION.show_default = True
PROFILE_BASE_OPTION = _option_with_value(
    None,
    "--profile-base",
    help="Override the base directory used to resolve relative profile env_file paths.",
)
GENERATE_OUTPUT_OPTION = _option_with_value(
    None,
    "--output",
    "-o",
    help="Where to write the generated file.",
)
ENV_FILE_ARGUMENT = typer.Argument(..., help="Path to the environment file.")
DIFF_FIRST_ARGUMENT = typer.Argument(..., help="Baseline environment file.")
DIFF_SECOND_ARGUMENT = typer.Argument(..., help="Target environment file.")

SPEC_OPTION_DEFAULT = cast(OptionalPath, SPEC_OPTION)
FORMAT_OPTION_DEFAULT = cast(str, FORMAT_OPTION)
PROFILE_OPTION_DEFAULT = cast(str, PROFILE_OPTION)
PROFILE_BASE_OPTION_DEFAULT = cast(OptionalPath, PROFILE_BASE_OPTION)
GENERATE_OUTPUT_OPTION_DEFAULT = cast(OptionalPath, GENERATE_OUTPUT_OPTION)


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2))


def _spec_base_dir(spec: Path) -> Path:
    """Return the directory used as the reference point for spec-relative paths."""

    return spec.parent.resolve() if str(spec) != "-" else Path.cwd()


def _resolve_profile_path(raw: str, *, base_dir: Path) -> Path:
    """Return an absolute profile path, honoring relative and user-expanded inputs."""

    candidate = Path(raw).expanduser()
    if raw == "-" or candidate.is_absolute():
        return candidate
    return (base_dir / candidate).resolve()


def _read_spec_input(spec: Path | None) -> tuple[str, str | None]:
    """Return the spec path string plus stdin contents when ``spec`` is ``-``."""
    if spec is None:
        config = load_config()
        spec = config.spec_path

    if spec is None:
        spec = find_spec_path()
        if spec is None:
            raise typer.BadParameter("spec file not found (envkeep.toml)")
    spec_path = str(spec)
    if spec_path == "-":
        return spec_path, sys.stdin.read()
    return spec_path, None


def _resolve_profile_base_dir(profile_base: Path | None, *, default_base: Path) -> Path:
    """Validate and resolve the profile base directory for doctor/inspect commands."""
    if profile_base is None:
        config = load_config()
        profile_base = config.profile_base

    if profile_base is None:
        return default_base
    candidate = profile_base.expanduser()
    if not candidate.exists():
        raise typer.BadParameter(f"profile base '{candidate}' does not exist")
    if not candidate.is_dir():
        raise typer.BadParameter(f"profile base '{candidate}' is not a directory")
    return candidate.resolve()


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
    limit = normalized_limit(summary_top)
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
    limit = normalized_limit(summary_top)
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
    limit = normalized_limit(top_limit)
    totals = report.severity_totals()
    ordered = [
        ("Errors", IssueSeverity.ERROR.value),
        ("Warnings", IssueSeverity.WARNING.value),
        ("Info", IssueSeverity.INFO.value),
    ]
    parts = [f"{label}: {totals[key]}" for label, key in ordered if totals[key] > 0]
    if not parts:
        parts = [f"{label}: {totals[key]}" for label, key in ordered]
    top_variables: tuple[str, ...]
    if limit == 0:
        top_variables = ()
    else:
        top_source = report.top_variables(None if limit is None else limit)
        top_variables = tuple(name for name, _ in top_source)
    if top_variables:
        parts.append("Impacted: " + ", ".join(top_variables))
    return " · ".join(parts)


def _format_diff_summary(report: DiffReport, *, top_limit: int | None) -> str:
    limit = normalized_limit(top_limit)
    summary = report.counts_by_kind()
    ordered = [
        ("Missing", DiffKind.MISSING.value),
        ("Extra", DiffKind.EXTRA.value),
        ("Changed", DiffKind.CHANGED.value),
    ]
    parts = [f"{label}: {summary[key]}" for label, key in ordered if summary[key] > 0]
    if not parts:
        parts = [f"{label}: {summary[key]}" for label, key in ordered]
    top_variables: tuple[str, ...]
    if limit == 0:
        top_variables = ()
    else:
        top_source = report.top_variables(None if limit is None else limit)
        top_variables = tuple(name for name, _ in top_source)
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
    profile_base_dir: str,
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
    non_empty_severities = [key for key, value in severity_totals.items() if value > 0]
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
        "profile_base_dir": profile_base_dir,
    }
    warnings_payload = {
        "duplicates": casefold_sorted(aggregated_duplicates),
        "extra_variables": casefold_sorted(aggregated_extras),
        "invalid_lines": sorted(
            aggregated_invalid_lines,
            key=lambda item: (
                item.get("profile", ""),
                *line_number_sort_key(item.get("line", "")),
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


def _load_spec_from_path(path: Path, stdin_data: str | None) -> EnvSpec:
    """Load a spec from a path, handling stdin."""
    path_str = str(path)
    try:
        if path_str == "-":
            content = stdin_data if stdin_data is not None else sys.stdin.read()
            if not content.strip():
                raise typer.BadParameter("spec input from stdin is empty")
            data = tomllib.loads(content)
            return EnvSpec.from_dict(data)
        return EnvSpec.from_file(path)
    except FileNotFoundError as exc:
        raise typer.BadParameter(f"spec file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        detail = getattr(exc, "msg", str(exc))
        line = getattr(exc, "lineno", None)
        col = getattr(exc, "colno", None)
        if line is not None and col is not None:
            detail = f"{detail} (line {line}, column {col})"
        message = f"failed to parse spec: {detail}"
        typer.echo(message)
        raise typer.BadParameter(message) from exc
    except Exception as exc:
        raise typer.BadParameter(f"failed to load spec: {exc}") from exc


def _merge_specs(base_spec: EnvSpec, imported_spec: EnvSpec) -> None:
    """Merge an imported spec into a base spec."""
    existing_vars = {var.name for var in base_spec.variables}
    base_spec.variables.extend(
        var for var in imported_spec.variables if var.name not in existing_vars
    )
    existing_profiles = {prof.name for prof in base_spec.profiles}
    base_spec.profiles.extend(
        prof for prof in imported_spec.profiles if prof.name not in existing_profiles
    )


def load_spec(path: Path | None, *, stdin_data: str | None = None) -> EnvSpec:
    if path is None:
        config = load_config()
        path = config.spec_path

    if path is None:
        path = find_spec_path()
        if path is None:
            raise typer.BadParameter("spec file not found (envkeep.toml)")

    base_spec = _load_spec_from_path(path, stdin_data)
    if not base_spec.imports:
        return base_spec

    base_dir = path.parent
    for import_path_str in base_spec.imports:
        import_path = base_dir / import_path_str
        imported_spec = load_spec(import_path)
        _merge_specs(base_spec, imported_spec)

    return base_spec


@app.command()
def check(
    env_file: Path = ENV_FILE_ARGUMENT,
    spec: OptionalPath = SPEC_OPTION_DEFAULT,
    output_format: str = FORMAT_OPTION_DEFAULT,
    allow_extra: bool = typer.Option(
        False,
        "--allow-extra",
        help="Allow variables not declared in the spec.",
    ),
    fail_on_warnings: bool = typer.Option(
        False,
        "--fail-on-warnings",
        help="Treat warnings as errors for CI enforcement.",
    ),
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables/codes shown in summaries (0 to suppress).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable caching of validation reports.",
    ),
) -> None:
    """Validate an environment against the specification."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")
    env_path = str(env_file)
    spec_path_str, stdin_spec = _read_spec_input(spec)
    spec_path = Path(spec_path_str) if spec_path_str else None
    if spec_path_str == "-" and env_path == "-":
        _usage_error("cannot read both spec and environment from stdin")
    env_spec = load_spec(spec_path, stdin_data=stdin_spec)

    cache = Cache() if not no_cache else None

    report = cache.get_report(env_file, spec_path) if cache and spec_path else None
    if report is None:
        # Fetch remote values from plugins
        remote_values = _fetch_remote_values(env_spec)

        if env_path == "-":
            data = sys.stdin.read()
            snapshot = EnvSnapshot.from_text(data, source="stdin")
        else:
            snapshot = EnvSnapshot.from_env_file(env_file)

        # Merge local and remote values, with remote taking precedence
        combined_values = snapshot.to_dict()
        combined_values.update(remote_values)

        # Create a new snapshot from the combined values for validation
        combined_snapshot = EnvSnapshot.from_dict(combined_values, source=str(env_file))

        report = env_spec.validate(combined_snapshot, allow_extra=allow_extra)
        if cache and spec_path:
            cache.set_report(env_file, spec_path, report)

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
    first: Path = DIFF_FIRST_ARGUMENT,
    second: Path = DIFF_SECOND_ARGUMENT,
    spec: OptionalPath = SPEC_OPTION_DEFAULT,
    output_format: str = FORMAT_OPTION_DEFAULT,
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables shown in summaries (0 to suppress).",
    ),
) -> None:
    """Compare two environment files using the spec for normalization."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")
    spec_path_str, stdin_spec = _read_spec_input(spec)
    minus_count = sum(1 for candidate in (str(first), str(second)) if candidate == "-")
    if spec_path_str == "-" and minus_count:
        _usage_error("cannot combine spec from stdin with environment stdin input")
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
    spec: OptionalPath = SPEC_OPTION_DEFAULT,
    output: OptionalPath = GENERATE_OUTPUT_OPTION_DEFAULT,
    no_redact_secrets: bool = typer.Option(
        False,
        "--no-redact-secrets",
        help="Disable masking for variables marked as secret.",
    ),
) -> None:
    """Generate a sanitized .env example from the spec."""

    _, stdin_spec = _read_spec_input(spec)
    env_spec = load_spec(spec, stdin_data=stdin_spec)
    content = env_spec.generate_example(redact_secrets=not no_redact_secrets)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote example to {output}")
    else:
        typer.echo(content)


@app.command()
def inspect(
    spec: OptionalPath = SPEC_OPTION_DEFAULT,
    output_format: str = FORMAT_OPTION_DEFAULT,
    profile_base: OptionalPath = PROFILE_BASE_OPTION_DEFAULT,
) -> None:
    """Print a summary of variables and profiles declared in the spec."""
    config = load_config()
    spec_path_resolved = spec or config.spec_path
    profile_base_path = resolve_optional_path_option(profile_base) or config.profile_base

    spec_path_str, stdin_spec = _read_spec_input(spec_path_resolved)
    spec_path = Path(spec_path_str)
    spec_base = _spec_base_dir(spec_path)
    profile_base_dir = _resolve_profile_base_dir(profile_base_path, default_base=spec_base)
    env_spec = load_spec(Path(spec_path_str) if spec_path_str else None, stdin_data=stdin_spec)
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
        profiles_payload = []
        for profile in env_spec.profiles:
            resolved_path = _resolve_profile_path(
                profile.env_file,
                base_dir=profile_base_dir,
            )
            profiles_payload.append(
                {
                    "name": profile.name,
                    "env_file": profile.env_file,
                    "resolved_env_file": str(resolved_path),
                    "description": profile.description,
                },
            )
        payload = {
            "summary": env_spec.summary(),
            "variables": variables_payload,
            "profiles": profiles_payload,
            "profile_base_dir": str(profile_base_dir),
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
            resolved_path = _resolve_profile_path(
                profile.env_file,
                base_dir=profile_base_dir,
            )
            descriptor = profile.description or profile.env_file
            if descriptor:
                descriptor = f"{descriptor} ({resolved_path})"
            else:
                descriptor = str(resolved_path)
            table.add_row(
                f"• {profile.name}",
                "",
                "",
                "",
                descriptor,
            )
    console.print(table)


def _aggregate_doctor_results(
    results: list[dict[str, Any]],
    top_limit: int,
) -> dict[str, Any]:
    """Aggregate results from multiple doctor reports."""
    total_errors = 0
    total_warnings = 0
    total_info = 0
    aggregate_warning_counts = {
        "duplicates": 0,
        "extra_variables": 0,
        "invalid_lines": 0,
    }
    aggregate_issue_variables: set[str] = set()
    aggregated_codes: Counter[str] = Counter()
    aggregated_variables: set[str] = set()
    aggregated_variable_counts: Counter[str] = Counter()

    for item in results:
        report = item.get("report")
        if not report:
            continue

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

    aggregated_most_common_codes = sorted_counter(aggregated_codes)
    aggregated_top_variables = sorted_counter(aggregated_variable_counts)
    if top_limit == 0:
        aggregated_most_common_codes = []
        aggregated_top_variables = []
    else:
        aggregated_most_common_codes = aggregated_most_common_codes[:top_limit]
        aggregated_top_variables = aggregated_top_variables[:top_limit]

    return {
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "total_info": total_info,
        "aggregate_warning_counts": aggregate_warning_counts,
        "aggregate_issue_variables": aggregate_issue_variables,
        "aggregated_most_common_codes": aggregated_most_common_codes,
        "aggregated_top_variables": aggregated_top_variables,
        "aggregated_variables_list": casefold_sorted(aggregated_variables),
    }


def _render_doctor_text_summary(
    checked_profiles: int,
    selected_profiles: int,
    missing_profiles: int,
    aggregated_results: dict[str, Any],
    top_limit: int,
    resolved_profile_records: list[tuple[str, str, Path, bool]],
) -> None:
    """Render the text summary for the doctor command."""
    console.rule("Doctor Summary")
    console.print(f"Profiles checked: {checked_profiles}/{selected_profiles}")
    console.print(
        " · ".join(
            [
                f"Missing profiles: {missing_profiles}",
                f"Total errors: {aggregated_results['total_errors']}",
                f"Total warnings: {aggregated_results['total_warnings']}",
                f"Total info: {aggregated_results['total_info']}",
            ],
        ),
    )
    console.print(
        "Warnings breakdown: "
        f"Duplicates: {aggregated_results['aggregate_warning_counts']['duplicates']} · "
        f"Extra variables: {aggregated_results['aggregate_warning_counts']['extra_variables']} · "
        f"Invalid lines: {aggregated_results['aggregate_warning_counts']['invalid_lines']}",
    )
    if aggregated_results["aggregate_issue_variables"]:
        sorted_variables = casefold_sorted(aggregated_results["aggregate_issue_variables"])
        if top_limit is not None:
            display_count = min(len(sorted_variables), top_limit)
        else:
            display_count = len(sorted_variables)
        console.print("Impacted variables: " + ", ".join(sorted_variables[:display_count]))
    else:
        console.print("Impacted variables: ")
    if aggregated_results["aggregated_most_common_codes"]:
        formatted_codes = ", ".join(
            f"{code}({count})" for code, count in aggregated_results["aggregated_most_common_codes"]
        )
        console.print(f"Top issue codes: {formatted_codes}")
    if aggregated_results["aggregated_top_variables"]:
        formatted_variables = ", ".join(
            f"{variable}({count})"
            for variable, count in aggregated_results["aggregated_top_variables"]
        )
        console.print(f"Top impacted variables: {formatted_variables}")
    else:
        console.print("Top impacted variables: ")
    if resolved_profile_records:
        console.print("Resolved profile paths:")
        for name, env_file_raw, resolved_path, exists in resolved_profile_records:
            status = "" if exists else " (missing)"
            console.print(f"  • {name}: {env_file_raw} -> {resolved_path}{status}")


@app.command()
def doctor(
    spec: OptionalPath = SPEC_OPTION_DEFAULT,
    profile: str = PROFILE_OPTION_DEFAULT,
    output_format: str = FORMAT_OPTION_DEFAULT,
    profile_base: OptionalPath = PROFILE_BASE_OPTION_DEFAULT,
    allow_extra: bool = typer.Option(
        False,
        "--allow-extra",
        help="Allow extra variables when validating profiles.",
    ),
    fail_on_warnings: bool = typer.Option(
        False,
        "--fail-on-warnings",
        help="Fail when any profile emits warnings.",
    ),
    summary_top: int = typer.Option(
        3,
        "--summary-top",
        help="Limit top impacted variables/codes shown in summaries (0 to suppress).",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Disable caching of validation reports.",
    ),
) -> None:
    """Validate one or more profiles declared in the spec."""

    if summary_top < 0:
        _usage_error("summary limit must be non-negative")

    config = load_config()
    spec_path_resolved = spec or config.spec_path
    profile_base_path = resolve_optional_path_option(profile_base) or config.profile_base

    spec_path_str, stdin_spec = _read_spec_input(spec_path_resolved)
    spec_path = Path(spec_path_str)
    spec_base = _spec_base_dir(spec_path)
    profile_base_dir = _resolve_profile_base_dir(profile_base_path, default_base=spec_base)
    env_spec = load_spec(Path(spec_path_str) if spec_path_str else None, stdin_data=stdin_spec)
    profiles = list(env_spec.iter_profiles())
    if not profiles:
        typer.echo("No profiles declared in spec.")
        raise typer.Exit(code=0)

    cache = Cache() if not no_cache else None

    def _selected_entry(item: ProfileSpec) -> dict[str, Any]:
        resolved = _resolve_profile_path(item.env_file, base_dir=profile_base_dir)
        return {
            "name": item.name,
            "env_file": item.env_file,
            "path": resolved,
        }

    if profile == "all":
        selected_profiles = [_selected_entry(item) for item in profiles]
    else:
        mapping = env_spec.profiles_by_name()
        if profile not in mapping:
            raise typer.BadParameter(f"profile '{profile}' not found")
        selected_profiles = [_selected_entry(mapping[profile])]

    exit_code = 0
    fmt = _coerce_output_format(output_format)
    use_json = fmt is OutputFormat.JSON
    results: list[dict[str, Any]] = []
    missing_profiles = 0
    checked_profiles = 0
    top_limit = normalized_limit(summary_top) or 0
    resolved_profile_records: list[tuple[str, str, Path, bool]] = []
    for entry in selected_profiles:
        name = entry["name"]
        env_file_raw = entry["env_file"]
        env_path = entry["path"]
        exists = env_path.exists()
        resolved_profile_records.append((name, env_file_raw, env_path, exists))
        if not exists:
            missing_profiles += 1
            if use_json:
                results.append(
                    {
                        "profile": name,
                        "env_file": env_file_raw,
                        "resolved_env_file": str(env_path),
                        "path": str(env_path),
                        "error": "missing env file",
                    },
                )
            else:
                typer.echo(f"Profile {name}: missing env file {env_path}")
            exit_code = 1
            continue

        report = cache.get_report(env_path, spec_path) if cache else None
        if report is None:
            snapshot = EnvSnapshot.from_env_file(env_path)
            report = env_spec.validate(snapshot, allow_extra=allow_extra)
            if cache:
                cache.set_report(env_path, spec_path, report)

        checked_profiles += 1
        if use_json:
            summary = report.summary(top_limit=top_limit)

            results.append(
                {
                    "profile": name,
                    "env_file": env_file_raw,
                    "resolved_env_file": str(env_path),
                    "path": str(env_path),
                    "report": report,
                    "summary": summary,
                    "warnings": report.warning_summary(),
                },
            )
        else:
            console.rule(f"Profile: {name}")
            render_validation_report(report, source=str(env_path), top_limit=top_limit)
        if report.has_errors or (fail_on_warnings and report.has_warnings):
            exit_code = 1

    aggregated_results = _aggregate_doctor_results(results, top_limit)

    if use_json:
        for result in results:
            if "report" in result:
                result["report"] = result["report"].to_dict(top_limit=top_limit)
        _emit_doctor_json(
            results,
            allow_extra=allow_extra,
            fail_on_warnings=fail_on_warnings,
            top_limit=top_limit,
            aggregated_codes=aggregated_results["aggregated_most_common_codes"],
            aggregated_top_variables=aggregated_results["aggregated_top_variables"],
            aggregated_variables=aggregated_results["aggregated_variables_list"],
            profile_base_dir=str(profile_base_dir),
        )
    else:
        _render_doctor_text_summary(
            checked_profiles,
            len(selected_profiles),
            missing_profiles,
            aggregated_results,
            top_limit,
            resolved_profile_records,
        )
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
