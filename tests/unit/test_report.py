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
    assert summary["issue_count"] == 3
    assert summary["has_errors"] is True
    assert summary["has_warnings"] is True
    assert summary["has_info"] is True
    assert summary["non_empty_severities"] == [
        IssueSeverity.ERROR.value,
        IssueSeverity.WARNING.value,
        IssueSeverity.INFO.value,
    ]
    assert summary["variables"] == ["A", "B", "C"]
    assert summary["most_common_codes"] == [
        ("extra", 1),
        ("missing", 1),
        ("note", 1),
    ]
    assert summary["variables_by_severity"][IssueSeverity.ERROR.value] == ["A"]
    assert summary["variables_by_severity"][IssueSeverity.WARNING.value] == ["B"]
    assert summary["variables_by_severity"][IssueSeverity.INFO.value] == ["C"]
    assert summary["top_variables"] == [
        ("A", 1),
        ("B", 1),
        ("C", 1),
    ]
    assert report.issue_count == 3
    assert len(report) == 3
    assert list(report)[0].variable == "A"
    assert report.counts_by_code() == {"extra": 1, "missing": 1, "note": 1}
    assert report.most_common_codes() == [
        ("extra", 1),
        ("missing", 1),
        ("note", 1),
    ]
    assert report.non_empty_severities() == (
        IssueSeverity.ERROR,
        IssueSeverity.WARNING,
        IssueSeverity.INFO,
    )
    assert report.variables_by_severity()[IssueSeverity.INFO.value] == ["C"]
    assert report.top_variables(2) == [
        ("A", 1),
        ("B", 1),
    ]
    assert report.has_variable("A") is True
    assert report.has_variable("Z") is False
    assert [issue.variable for issue in report.issues_for("A")] == ["A"]
    payload = report.to_dict()
    assert payload["severity_totals"][IssueSeverity.ERROR.value] == 1
    assert payload["codes"] == {"extra": 1, "missing": 1, "note": 1}
    assert payload["most_common_codes"] == [
        ("extra", 1),
        ("missing", 1),
        ("note", 1),
    ]
    assert payload["non_empty_severities"] == [
        IssueSeverity.ERROR.value,
        IssueSeverity.WARNING.value,
        IssueSeverity.INFO.value,
    ]
    assert payload["variables"] == ["A", "B", "C"]
    limited_summary = report.summary(top_limit=1)
    assert limited_summary["top_variables"] == [("A", 1)]
    assert limited_summary["most_common_codes"] == [("extra", 1)]
    limited_payload = report.to_dict(top_limit=0)
    assert limited_payload["top_variables"] == []
    assert limited_payload["most_common_codes"] == []
    totals = report.severity_totals()
    assert totals == {"error": 1, "warning": 1, "info": 1}
    assert report.has_errors is True
    assert report.has_warnings is True
    assert report.has_info is True
    assert [issue.variable for issue in report.issues_by_code("missing")] == ["A"]
    assert report.issues_by_code("absent") == []
    assert report.codes() == ("extra", "missing", "note")
    assert report.variables() == ("A", "B", "C")
    assert report.has_code("extra") is True
    assert report.has_code("absent") is False
    assert report.codes() == ("extra", "missing", "note")


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
    assert summary["is_clean"] is False
    assert len(report) == 3
    assert report.count_for(DiffKind.EXTRA) == 1
    assert report.count_for(DiffKind.MISSING) == 1
    assert report.count_for(DiffKind.CHANGED) == 1
    assert report.has_kind(DiffKind.EXTRA) is True
    assert report.has_kind(DiffKind.CHANGED) is True
    assert report.counts_by_kind()[DiffKind.EXTRA.value] == 1
    assert [entry.variable for entry in report.entries_by_kind(DiffKind.EXTRA)] == ["A"]
    assert report.non_empty_kinds() == (
        DiffKind.MISSING,
        DiffKind.EXTRA,
        DiffKind.CHANGED,
    )
    assert report.variables() == ("A", "B", "C")
    assert report.has_variable("A") is True
    assert report.has_variable("Z") is False
    assert report.variables_by_kind()[DiffKind.MISSING.value] == ["B"]
    assert report.top_variables(2) == [
        ("A", 1),
        ("B", 1),
    ]
    payload = report.to_dict()
    assert payload["is_clean"] is False
    assert payload["by_kind"][DiffKind.CHANGED.value] == 1
    assert payload["variables"] == ["A", "B", "C"]
    assert payload["variables_by_kind"][DiffKind.EXTRA.value] == ["A"]
    assert payload["top_variables"] == [
        ("A", 1),
        ("B", 1),
        ("C", 1),
    ]
    limited_summary = report.summary(top_limit=1)
    assert limited_summary["top_variables"] == [("A", 1)]
    limited_payload = report.to_dict(top_limit=0)
    assert limited_payload["top_variables"] == []
    assert summary["non_empty_kinds"] == [
        DiffKind.MISSING.value,
        DiffKind.EXTRA.value,
        DiffKind.CHANGED.value,
    ]
    assert summary["variables"] == ["A", "B", "C"]
    assert summary["variables_by_kind"][DiffKind.CHANGED.value] == ["C"]
    assert summary["top_variables"] == [
        ("A", 1),
        ("B", 1),
        ("C", 1),
    ]


def test_validation_report_counters_update_incrementally() -> None:
    report = ValidationReport()
    report.add(
        ValidationIssue(
            variable="FOO",
            message="missing",
            severity=IssueSeverity.ERROR,
            code="missing",
        )
    )
    report.extend(
        ValidationIssue(
            variable="BAR",
            message="warning",
            severity=IssueSeverity.WARNING,
            code="extra",
        )
        for _ in range(2)
    )
    assert report.error_count == 1
    assert report.warning_count == 2
    summary = report.summary()
    assert summary["severity_totals"][IssueSeverity.ERROR.value] == 1
    assert summary["severity_totals"][IssueSeverity.WARNING.value] == 2
    assert summary["codes"] == {"missing": 1, "extra": 2}


def test_diff_report_sorted_entries_orders_by_kind_then_name() -> None:
    report = DiffReport(
        entries=[
            DiffEntry(variable="B", kind=DiffKind.CHANGED, left="1", right="2", secret=False),
            DiffEntry(variable="A", kind=DiffKind.EXTRA, left=None, right="1", secret=False),
            DiffEntry(variable="C", kind=DiffKind.MISSING, left="1", right=None, secret=False),
        ]
    )
    ordered = report.sorted_entries()
    assert [entry.kind for entry in ordered] == [
        DiffKind.MISSING,
        DiffKind.EXTRA,
        DiffKind.CHANGED,
    ]
    assert [entry.variable for entry in ordered] == ["C", "A", "B"]


def test_validation_report_most_common_codes_limit() -> None:
    report = ValidationReport()
    entries = [
        ValidationIssue(variable=f"VAR_{idx}", message="warn", severity=IssueSeverity.WARNING, code="extra")
        for idx in range(3)
    ]
    report.extend(entries)
    report.add(
        ValidationIssue(
            variable="VAR_SPECIAL",
            message="duplicate",
            severity=IssueSeverity.WARNING,
            code="duplicate",
        )
    )
    assert report.most_common_codes(limit=1) == [("extra", 3)]


def test_validation_report_warning_summary_orders_entries() -> None:
    report = ValidationReport()
    report.extend(
        [
            ValidationIssue(
                variable="beta",
                message="unexpected variable",
                severity=IssueSeverity.WARNING,
                code="extra",
            ),
            ValidationIssue(
                variable="ALPHA",
                message="unexpected variable",
                severity=IssueSeverity.WARNING,
                code="extra",
            ),
            ValidationIssue(
                variable="zeta",
                message="duplicate declaration",
                severity=IssueSeverity.WARNING,
                code="duplicate",
            ),
            ValidationIssue(
                variable="Alpha",
                message="duplicate declaration",
                severity=IssueSeverity.WARNING,
                code="duplicate",
            ),
            ValidationIssue(
                variable="line 10",
                message="line could not be parsed",
                severity=IssueSeverity.WARNING,
                code="invalid_line",
                hint="check spacing",
            ),
            ValidationIssue(
                variable="line 2",
                message="line could not be parsed",
                severity=IssueSeverity.WARNING,
                code="invalid_line",
                hint="missing equals",
            ),
        ]
    )
    summary = report.warning_summary()
    assert summary["total"] == report.warning_count == 6
    assert summary["extra_variables"] == ["ALPHA", "beta"]
    assert summary["duplicates"] == ["Alpha", "zeta"]
    assert summary["invalid_lines"] == [
        {"line": "line 2", "hint": "missing equals"},
        {"line": "line 10", "hint": "check spacing"},
    ]
