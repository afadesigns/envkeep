from __future__ import annotations

from envkeep.report import (
    DiffEntry,
    DiffKind,
    DiffReport,
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
)


def test_validation_report_summary_counts() -> None:
    report = ValidationReport(
        issues=[
            ValidationIssue(variable="A", message="boom", severity=IssueSeverity.ERROR, code="missing"),
            ValidationIssue(variable="B", message="warn", severity=IssueSeverity.WARNING, code="extra"),
            ValidationIssue(variable="C", message="info", severity=IssueSeverity.INFO, code="note"),
        ]
    )
    summary = report.summary()
    assert summary["severity_totals"][IssueSeverity.ERROR.value] == 1
    assert summary["severity_totals"][IssueSeverity.WARNING.value] == 1
    assert summary["severity_totals"][IssueSeverity.INFO.value] == 1
    assert summary["codes"] == {"missing": 1, "extra": 1, "note": 1}


def test_diff_report_summary_counts() -> None:
    report = DiffReport(
        entries=[
            DiffEntry(variable="A", kind=DiffKind.EXTRA, left=None, right="1", secret=False),
            DiffEntry(variable="B", kind=DiffKind.MISSING, left="1", right=None, secret=False),
            DiffEntry(variable="C", kind=DiffKind.CHANGED, left="1", right="2", secret=False),
        ]
    )
    summary = report.summary()
    assert summary["change_count"] == 3
    assert summary["by_kind"] == {
        DiffKind.MISSING.value: 1,
        DiffKind.EXTRA.value: 1,
        DiffKind.CHANGED.value: 1,
    }
