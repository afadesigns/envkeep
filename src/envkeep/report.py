from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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

    @property
    def is_success(self) -> bool:
        return all(issue.severity != IssueSeverity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == IssueSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == IssueSeverity.WARNING)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, issues: list[ValidationIssue]) -> None:
        self.issues.extend(issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_success": self.is_success,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def summary(self) -> dict[str, Any]:
        severity_totals = {
            IssueSeverity.ERROR.value: self.error_count,
            IssueSeverity.WARNING.value: self.warning_count,
            IssueSeverity.INFO.value: sum(1 for issue in self.issues if issue.severity == IssueSeverity.INFO),
        }
        codes: dict[str, int] = {}
        for issue in self.issues:
            codes[issue.code] = codes.get(issue.code, 0) + 1
        return {
            "is_success": self.is_success,
            "severity_totals": severity_totals,
            "codes": codes,
        }


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

    @property
    def change_count(self) -> int:
        return len(self.entries)

    def is_clean(self) -> bool:
        return not self.entries

    def add(self, entry: DiffEntry) -> None:
        self.entries.append(entry)

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_count": self.change_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def summary(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {kind.value: 0 for kind in DiffKind}
        for entry in self.entries:
            by_kind[entry.kind.value] += 1
        return {
            "change_count": self.change_count,
            "by_kind": by_kind,
        }


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    return "***"
