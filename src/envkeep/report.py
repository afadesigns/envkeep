from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator


class IssueSeverity(str, Enum):
    """Represents the severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class ValidationIssue:
    """Single validation issue produced while evaluating a snapshot."""

    variable: str
    message: str
    severity: IssueSeverity
    code: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "message": self.message,
            "severity": self.severity.value,
            "code": self.code,
            "hint": self.hint,
        }


@dataclass(slots=True)
class ValidationReport:
    """Collection of validation issues along with derived summary flags."""

    issues: list[ValidationIssue] = field(default_factory=list)
    _severity_counts: Counter[IssueSeverity] = field(init=False, repr=False)
    _code_counts: Counter[str] = field(init=False, repr=False)
    _variable_counts: Counter[str] = field(init=False, repr=False)
    _severity_buckets: dict[IssueSeverity, list[ValidationIssue]] = field(init=False, repr=False)
    _code_buckets: dict[str, list[ValidationIssue]] = field(init=False, repr=False)
    _issue_sort_key = staticmethod(
        lambda issue: (
            issue.variable.casefold(),
            issue.variable,
            issue.code,
            issue.message,
            issue.hint or "",
        )
    )

    def __post_init__(self) -> None:
        self._severity_counts = Counter()
        self._code_counts = Counter()
        self._severity_buckets = {severity: [] for severity in IssueSeverity}
        self._code_buckets: dict[str, list[ValidationIssue]] = {}
        self._variable_counts = Counter()
        if self.issues:
            captured = list(self.issues)
            self.issues.clear()
            self.extend(captured)

    @property
    def is_success(self) -> bool:
        return self.error_count == 0

    @property
    def error_count(self) -> int:
        return self._severity_counts.get(IssueSeverity.ERROR, 0)

    @property
    def warning_count(self) -> int:
        return self._severity_counts.get(IssueSeverity.WARNING, 0)

    @property
    def info_count(self) -> int:
        return self._severity_counts.get(IssueSeverity.INFO, 0)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        return self.warning_count > 0

    @property
    def has_info(self) -> bool:
        return self.info_count > 0

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return self.issue_count

    def __iter__(self) -> Iterator[ValidationIssue]:  # pragma: no cover - trivial
        return iter(self.issues)

    def _track_issue(self, issue: ValidationIssue) -> None:
        self._severity_counts[issue.severity] += 1
        self._code_counts[issue.code] += 1
        self._variable_counts[issue.variable] += 1
        self._severity_buckets[issue.severity].append(issue)
        self._code_buckets.setdefault(issue.code, []).append(issue)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        self._track_issue(issue)

    def extend(self, issues: Iterable[ValidationIssue]) -> None:
        for issue in issues:
            self.issues.append(issue)
            self._track_issue(issue)

    def severity_totals(self) -> dict[str, int]:
        return {
            IssueSeverity.ERROR.value: self.error_count,
            IssueSeverity.WARNING.value: self.warning_count,
            IssueSeverity.INFO.value: self.info_count,
        }

    def counts_by_code(self) -> dict[str, int]:
        return {code: self._code_counts[code] for code in sorted(self._code_counts)}

    def most_common_codes(self, limit: int | None = None) -> list[tuple[str, int]]:
        items = self._code_counts.most_common()
        sorted_items = sorted(items, key=lambda item: (-item[1], item[0]))
        if limit is not None:
            return sorted_items[:limit]
        return sorted_items

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._code_counts))

    def variables(self) -> tuple[str, ...]:
        if not self.issues:
            return ()
        unique = {issue.variable for issue in self.issues}
        return tuple(sorted(unique, key=lambda name: (name.casefold(), name)))

    def has_code(self, code: str) -> bool:
        return code in self._code_counts

    def has_variable(self, variable: str) -> bool:
        return variable in self._variable_counts

    def issues_for(self, variable: str) -> list[ValidationIssue]:
        matches = [issue for issue in self.issues if issue.variable == variable]
        return sorted(matches, key=self._issue_sort_key)

    def variables_by_severity(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for severity in IssueSeverity:
            items = {
                issue.variable
                for issue in self._severity_buckets.get(severity, [])
            }
            mapping[severity.value] = sorted(
                items,
                key=lambda name: (name.casefold(), name),
            )
        return mapping

    def top_variables(self, limit: int | None = None) -> list[tuple[str, int]]:
        items = self._variable_counts.most_common()
        sorted_items = sorted(items, key=lambda item: (-item[1], item[0]))
        if limit is not None:
            return sorted_items[:limit]
        return sorted_items

    def non_empty_severities(self) -> tuple[IssueSeverity, ...]:
        order: tuple[IssueSeverity, ...] = (
            IssueSeverity.ERROR,
            IssueSeverity.WARNING,
            IssueSeverity.INFO,
        )
        return tuple(severity for severity in order if self._severity_counts.get(severity, 0) > 0)

    @staticmethod
    def _normalize_limit(limit: int | None) -> int | None:
        if limit is None:
            return None
        return max(limit, 0)

    def to_dict(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = self._normalize_limit(top_limit)
        return {
            "is_success": self.is_success,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issue_count": self.issue_count,
            "severity_totals": self.severity_totals(),
            "codes": self.counts_by_code(),
            "most_common_codes": self.most_common_codes(limit),
            "non_empty_severities": [severity.value for severity in self.non_empty_severities()],
            "variables": list(self.variables()),
            "variables_by_severity": self.variables_by_severity(),
            "top_variables": self.top_variables(limit),
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def summary(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = self._normalize_limit(top_limit)
        return {
            "is_success": self.is_success,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "has_info": self.has_info,
            "issue_count": self.issue_count,
            "severity_totals": self.severity_totals(),
            "codes": self.counts_by_code(),
            "most_common_codes": self.most_common_codes(limit),
            "non_empty_severities": [severity.value for severity in self.non_empty_severities()],
            "variables": list(self.variables()),
            "variables_by_severity": self.variables_by_severity(),
            "top_variables": self.top_variables(limit),
        }

    def issues_by_severity(self, severity: IssueSeverity) -> list[ValidationIssue]:
        bucket = self._severity_buckets.get(severity)
        if not bucket:
            return []
        return [*sorted(bucket, key=self._issue_sort_key)]

    def issues_by_code(self, code: str) -> list[ValidationIssue]:
        bucket = self._code_buckets.get(code)
        if not bucket:
            return []
        return [*sorted(bucket, key=self._issue_sort_key)]


class DiffKind(str, Enum):
    """Kind of difference discovered by the diff engine."""

    MISSING = "missing"
    EXTRA = "extra"
    CHANGED = "changed"


@dataclass(slots=True)
class DiffEntry:
    """Represents a single difference between two environment snapshots."""

    variable: str
    kind: DiffKind
    left: str | None
    right: str | None
    secret: bool

    def redacted_left(self) -> str | None:
        return _redact(self.left) if self.secret else self.left

    def redacted_right(self) -> str | None:
        return _redact(self.right) if self.secret else self.right

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "kind": self.kind.value,
            "left": self.redacted_left(),
            "right": self.redacted_right(),
            "secret": self.secret,
        }


@dataclass(slots=True)
class DiffReport:
    """Summarizes differences between two environment snapshots."""

    entries: list[DiffEntry] = field(default_factory=list)
    _counts: Counter[DiffKind] = field(init=False, repr=False)
    _kind_buckets: dict[DiffKind, list[DiffEntry]] = field(init=False, repr=False)
    _variable_counts: Counter[str] = field(init=False, repr=False)
    _kind_order: tuple[DiffKind, ...] = (
        DiffKind.MISSING,
        DiffKind.EXTRA,
        DiffKind.CHANGED,
    )

    def __post_init__(self) -> None:
        self._counts = Counter()
        self._kind_buckets: dict[DiffKind, list[DiffEntry]] = {kind: [] for kind in DiffKind}
        self._variable_counts = Counter()
        if self.entries:
            captured = list(self.entries)
            self.entries.clear()
            for entry in captured:
                self.add(entry)

    @property
    def change_count(self) -> int:
        return len(self.entries)

    def is_clean(self) -> bool:
        return not self.entries

    def __len__(self) -> int:  # pragma: no cover - trivial
        return self.change_count

    def _track_entry(self, entry: DiffEntry) -> None:
        self._counts[entry.kind] += 1
        self._kind_buckets.setdefault(entry.kind, []).append(entry)
        self._variable_counts[entry.variable] += 1

    def add(self, entry: DiffEntry) -> None:
        self.entries.append(entry)
        self._track_entry(entry)

    @staticmethod
    def _normalize_limit(limit: int | None) -> int | None:
        if limit is None:
            return None
        return max(limit, 0)

    def to_dict(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = self._normalize_limit(top_limit)
        return {
            "change_count": self.change_count,
            "is_clean": self.is_clean(),
            "by_kind": self.counts_by_kind(),
            "entries": [entry.to_dict() for entry in self.entries],
            "variables": list(self.variables()),
            "top_variables": self.top_variables(limit),
            "variables_by_kind": self.variables_by_kind(),
            "non_empty_kinds": [kind.value for kind in self.non_empty_kinds()],
        }

    def sorted_entries(self) -> list[DiffEntry]:
        order = {kind: index for index, kind in enumerate(self._kind_order)}
        return sorted(
            self.entries,
            key=lambda item: (
                order[item.kind],
                item.variable.casefold(),
                item.variable,
            ),
        )

    def entries_by_kind(self, kind: DiffKind) -> list[DiffEntry]:
        bucket = self._kind_buckets.get(kind)
        if not bucket:
            return []
        return [
            *sorted(
                bucket,
                key=lambda item: (item.variable.casefold(), item.variable),
            )
        ]

    def count_for(self, kind: DiffKind) -> int:
        return self._counts.get(kind, 0)

    def has_kind(self, kind: DiffKind) -> bool:
        return self.count_for(kind) > 0

    def non_empty_kinds(self) -> tuple[DiffKind, ...]:
        return tuple(kind for kind in self._kind_order if self.has_kind(kind))

    def variables(self) -> tuple[str, ...]:
        if not self.entries:
            return ()
        unique = {entry.variable for entry in self.entries}
        return tuple(sorted(unique, key=lambda name: (name.casefold(), name)))

    def has_variable(self, variable: str) -> bool:
        return variable in self._variable_counts

    def top_variables(self, limit: int | None = None) -> list[tuple[str, int]]:
        items = self._variable_counts.most_common()
        sorted_items = sorted(items, key=lambda item: (-item[1], item[0]))
        if limit is not None:
            return sorted_items[:limit]
        return sorted_items

    def variables_by_kind(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for kind in DiffKind:
            variables = {
                entry.variable
                for entry in self._kind_buckets.get(kind, [])
            }
            mapping[kind.value] = sorted(
                variables,
                key=lambda name: (name.casefold(), name),
            )
        return mapping

    def counts_by_kind(self) -> dict[str, int]:
        return {
            kind.value: self.count_for(kind)
            for kind in self._kind_order
        }

    def summary(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = self._normalize_limit(top_limit)
        return {
            "change_count": self.change_count,
            "is_clean": self.is_clean(),
            "by_kind": self.counts_by_kind(),
            "non_empty_kinds": [kind.value for kind in self.non_empty_kinds()],
            "variables": list(self.variables()),
            "top_variables": self.top_variables(limit),
            "variables_by_kind": self.variables_by_kind(),
        }


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    return "***"
