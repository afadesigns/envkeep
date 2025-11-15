from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from .report import DiffKind, DiffReport, IssueSeverity, ValidationReport


console = Console()


def render_validation_report(
    report: "ValidationReport",
    *,
    source: str,
    top_limit: int | None = None,
) -> None:
    console.print(f"Validating [bold]{source}[/bold]")
    if not report.issues:
        console.print("[green]All checks passed.[/green]")
        return
    style_map = {
        "error": "red",
        "warning": "yellow",
        "info": "blue",
    }
    label_map = {
        "error": "Errors",
        "warning": "Warnings",
        "info": "Info",
    }
    first_section = True
    for severity in report.non_empty_severities():
        issues = report.issues_by_severity(severity)
        if not first_section:
            console.print()
        first_section = False
        console.print(f"[bold underline]{label_map[severity.value]}[/]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Severity")
        table.add_column("Variable")
        table.add_column("Code")
        table.add_column("Message")
        table.add_column("Hint", overflow="fold")
        style = style_map[severity.value]
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
    report: "DiffReport",
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
        "missing": "yellow",
        "extra": "blue",
        "changed": "red",
    }
    label_map = {
        "missing": "Missing",
        "extra": "Extra",
        "changed": "Changed",
    }
    first_section = True
    for kind in report.non_empty_kinds():
        entries = report.entries_by_kind(kind)
        if not first_section:
            console.print()
        first_section = False
        console.print(f"[bold underline]{label_map[kind.value]}[/]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("Variable")
        table.add_column("Change")
        table.add_column("Left")
        table.add_column("Right")
        style = style_map[kind.value]
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


def _format_severity_summary(report: "ValidationReport", *, top_limit: int | None) -> str:
    from .cli import normalized_limit
    from .report import IssueSeverity

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


def _format_diff_summary(report: "DiffReport", *, top_limit: int | None) -> str:
    from .cli import normalized_limit
    from .report import DiffKind

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
