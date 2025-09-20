from __future__ import annotations

"""Reporting utilities with copy-on-read caches for envkeep CLI output."""

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterator

from .utils import normalized_limit


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
    """Collection of validation issues along with derived summary flags.

    Cached aggregates are stored internally but every public accessor returns
    copy-on-read data so callers cannot mutate the cached state accidentally.
    """

    issues: list[ValidationIssue] = field(default_factory=list)
    _severity_counts: Counter[IssueSeverity] = field(init=False, repr=False)
    _code_counts: Counter[str] = field(init=False, repr=False)
    _variable_counts: Counter[str] = field(init=False, repr=False)
    _severity_buckets: dict[IssueSeverity, list[ValidationIssue]] = field(init=False, repr=False)
    _code_buckets: dict[str, list[ValidationIssue]] = field(init=False, repr=False)
    _variable_buckets: dict[str, list[ValidationIssue]] = field(init=False, repr=False)
    _severity_variables: dict[IssueSeverity, set[str]] = field(init=False, repr=False)
    _severity_variable_cache: dict[IssueSeverity, tuple[str, ...]] = field(init=False, repr=False)
    _top_variables_cache: tuple[tuple[str, int], ...] | None = field(init=False, repr=False)
    _most_common_codes_cache: list[tuple[str, int]] | None = field(init=False, repr=False)
    _sorted_severity_cache: dict[IssueSeverity, tuple[ValidationIssue, ...]] = field(init=False, repr=False)
    _sorted_code_cache: dict[str, tuple[ValidationIssue, ...]] = field(init=False, repr=False)
    _sorted_variable_cache: dict[str, tuple[ValidationIssue, ...]] = field(init=False, repr=False)
    _counts_by_code_cache: tuple[tuple[str, int], ...] | None = field(init=False, repr=False)
    _counts_by_code_mapping: MappingProxyType[str, int] | None = field(init=False, repr=False)
    _variables_cache: tuple[str, ...] | None = field(init=False, repr=False)
    _warning_summary_cache: tuple[
        int,
        tuple[str, ...],
        tuple[str, ...],
        tuple[tuple[str, str], ...],
    ] | None = field(init=False, repr=False)
    _variables_by_severity_cache: dict[str, tuple[str, ...]] | None = field(init=False, repr=False)
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
        self._variable_buckets = {}
        self._severity_variables = {severity: set() for severity in IssueSeverity}
        self._severity_variable_cache = {}
        self._top_variables_cache = None
        self._most_common_codes_cache = None
        self._sorted_severity_cache = {}
        self._sorted_code_cache = {}
        self._sorted_variable_cache = {}
        self._counts_by_code_cache = None
        self._counts_by_code_mapping = None
        self._variables_cache = None
        self._warning_summary_cache = None
        self._variables_by_severity_cache = None
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

    def _invalidate_issue_caches(self, issue: ValidationIssue) -> None:
        self._severity_variable_cache.pop(issue.severity, None)
        self._sorted_severity_cache.pop(issue.severity, None)
        self._sorted_code_cache.pop(issue.code, None)
        self._sorted_variable_cache.pop(issue.variable, None)
        self._counts_by_code_cache = None
        self._counts_by_code_mapping = None
        self._variables_cache = None
        self._warning_summary_cache = None
        self._variables_by_severity_cache = None
        self._top_variables_cache = None
        self._most_common_codes_cache = None

    def _track_issue(self, issue: ValidationIssue) -> None:
        self._severity_counts[issue.severity] += 1
        self._code_counts[issue.code] += 1
        self._variable_counts[issue.variable] += 1
        self._severity_buckets[issue.severity].append(issue)
        self._code_buckets.setdefault(issue.code, []).append(issue)
        self._variable_buckets.setdefault(issue.variable, []).append(issue)
        self._severity_variables[issue.severity].add(issue.variable)
        self._invalidate_issue_caches(issue)

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

    def counts_by_code(self) -> Mapping[str, int]:
        if self._counts_by_code_mapping is None:
            if self._counts_by_code_cache is None:
                self._counts_by_code_cache = tuple(sorted(self._code_counts.items()))
            # Materialize once so MappingProxyType exposes a stable view
            self._counts_by_code_mapping = MappingProxyType(dict(self._counts_by_code_cache))
        return self._counts_by_code_mapping

    def most_common_codes(self, limit: int | None = None) -> list[tuple[str, int]]:
        if self._most_common_codes_cache is None:
            self._most_common_codes_cache = sorted(
                self._code_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        if limit is not None:
            return self._most_common_codes_cache[:limit]
        return [*self._most_common_codes_cache]

    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._code_counts))

    def variables(self) -> tuple[str, ...]:
        if self._variables_cache is not None:
            return self._variables_cache
        if not self._variable_counts:
            self._variables_cache = ()
            return ()
        computed = tuple(
            sorted(
                self._variable_counts,
                key=lambda name: (name.casefold(), name),
            )
        )
        self._variables_cache = computed
        return computed

    def has_code(self, code: str) -> bool:
        return code in self._code_counts

    def has_variable(self, variable: str) -> bool:
        return variable in self._variable_counts

    def issues_for(self, variable: str) -> list[ValidationIssue]:
        return [*self._sorted_variable_bucket(variable)]

    def variables_by_severity(self) -> dict[str, list[str]]:
        cached = self._variables_by_severity_cache
        if cached is None:
            cached = {
                severity.value: self._variables_for_severity(severity)
                for severity in IssueSeverity
            }
            self._variables_by_severity_cache = cached
        return {key: list(values) for key, values in cached.items()}

    def _variables_for_severity(self, severity: IssueSeverity) -> tuple[str, ...]:
        cached = self._severity_variable_cache.get(severity)
        if cached is not None:
            return cached
        computed = tuple(
            sorted(
                self._severity_variables[severity],
                key=lambda name: (name.casefold(), name),
            )
        )
        self._severity_variable_cache[severity] = computed
        return computed

    def top_variables(self, limit: int | None = None) -> Sequence[tuple[str, int]]:
        if self._top_variables_cache is None:
            self._top_variables_cache = tuple(
                sorted(
                    self._variable_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            )
        if limit is None:
            return list(self._top_variables_cache)
        if limit == 0:
            return []
        return list(self._top_variables_cache[:limit])

    def non_empty_severities(self) -> tuple[IssueSeverity, ...]:
        order: tuple[IssueSeverity, ...] = (
            IssueSeverity.ERROR,
            IssueSeverity.WARNING,
            IssueSeverity.INFO,
        )
        return tuple(severity for severity in order if self._severity_counts.get(severity, 0) > 0)

    def to_dict(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = normalized_limit(top_limit)
        return {
            "is_success": self.is_success,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issue_count": self.issue_count,
            "severity_totals": self.severity_totals(),
            "codes": dict(self.counts_by_code()),
            "most_common_codes": self.most_common_codes(limit),
            "non_empty_severities": [severity.value for severity in self.non_empty_severities()],
            "variables": list(self.variables()),
            "variables_by_severity": self.variables_by_severity(),
            "top_variables": self.top_variables(limit),
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def summary(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = normalized_limit(top_limit)
        return {
            "is_success": self.is_success,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "has_info": self.has_info,
            "issue_count": self.issue_count,
            "severity_totals": self.severity_totals(),
            "codes": dict(self.counts_by_code()),
            "most_common_codes": self.most_common_codes(limit),
            "non_empty_severities": [severity.value for severity in self.non_empty_severities()],
            "variables": list(self.variables()),
            "variables_by_severity": self.variables_by_severity(),
            "top_variables": self.top_variables(limit),
        }

    def issues_by_severity(self, severity: IssueSeverity) -> list[ValidationIssue]:
        cached = self._sorted_severity_cache.get(severity)
        if cached is not None:
            return [*cached]
        bucket = self._severity_buckets.get(severity)
        if not bucket:
            self._sorted_severity_cache[severity] = ()
            return []
        sorted_bucket = tuple(sorted(bucket, key=self._issue_sort_key))
        self._sorted_severity_cache[severity] = sorted_bucket
        return [*sorted_bucket]

    def issues_by_code(self, code: str) -> list[ValidationIssue]:
        return [*self._sorted_code_bucket(code)]

    def _sorted_variable_bucket(self, variable: str) -> tuple[ValidationIssue, ...]:
        cached = self._sorted_variable_cache.get(variable)
        if cached is not None:
            return cached
        bucket = self._variable_buckets.get(variable)
        if not bucket:
            self._sorted_variable_cache[variable] = ()
            return ()
        sorted_bucket = tuple(sorted(bucket, key=self._issue_sort_key))
        self._sorted_variable_cache[variable] = sorted_bucket
        return sorted_bucket

    def _sorted_code_bucket(self, code: str) -> tuple[ValidationIssue, ...]:
        cached = self._sorted_code_cache.get(code)
        if cached is not None:
            return cached
        bucket = self._code_buckets.get(code)
        if not bucket:
            self._sorted_code_cache[code] = ()
            return ()
        sorted_bucket = tuple(sorted(bucket, key=self._issue_sort_key))
        self._sorted_code_cache[code] = sorted_bucket
        return sorted_bucket

    @staticmethod
    def _casefold_sorted(values: Iterable[str]) -> list[str]:
        return sorted(set(values), key=lambda item: (item.casefold(), item))

    @staticmethod
    def _invalid_line_sort_key(value: str) -> tuple[int, str]:
        digits = "".join(char for char in value if char.isdigit())
        number = int(digits) if digits else 0
        return number, value

    def warning_summary(self) -> dict[str, Any]:
        cached = self._warning_summary_cache
        if cached is None:
            duplicate_issues = self._sorted_code_bucket("duplicate")
            extra_issues = self._sorted_code_bucket("extra")
            invalid_line_issues = self._sorted_code_bucket("invalid_line")
            duplicates = tuple(
                self._casefold_sorted(issue.variable for issue in duplicate_issues)
            )
            extras = tuple(
                self._casefold_sorted(issue.variable for issue in extra_issues)
            )
            invalid_lines = tuple(
                sorted(
                    (
                        (issue.variable, issue.hint or issue.message)
                        for issue in invalid_line_issues
                    ),
                    key=lambda item: self._invalid_line_sort_key(item[0]),
                )
            )
            cached = self._warning_summary_cache = (
                self.warning_count,
                duplicates,
                extras,
                invalid_lines,
            )
        total, duplicates, extras, invalid_lines = cached
        return {
            "total": total,
            "duplicates": list(duplicates),
            "extra_variables": list(extras),
            "invalid_lines": [
                {"line": line, "hint": hint}
                for line, hint in invalid_lines
            ],
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
    """Summarizes differences between two environment snapshots.

    Public accessors expose copy-on-read sequences/mappings while memoizing the
    underlying tuples for repeated CLI rendering.
    """

    entries: list[DiffEntry] = field(default_factory=list)
    _counts: Counter[DiffKind] = field(init=False, repr=False)
    _kind_buckets: dict[DiffKind, list[DiffEntry]] = field(init=False, repr=False)
    _variable_counts: Counter[str] = field(init=False, repr=False)
    _top_variables_cache: tuple[tuple[str, int], ...] | None = field(init=False, repr=False)
    _variables_by_kind_cache: dict[str, tuple[str, ...]] | None = field(init=False, repr=False)
    _sorted_kind_cache: dict[DiffKind, tuple[DiffEntry, ...]] = field(init=False, repr=False)
    _variables_cache: tuple[str, ...] | None = field(init=False, repr=False)
    _sorted_entries_cache: tuple[DiffEntry, ...] | None = field(init=False, repr=False)
    _counts_by_kind_mapping: MappingProxyType[str, int] | None = field(init=False, repr=False)
    _kind_order: tuple[DiffKind, ...] = (
        DiffKind.MISSING,
        DiffKind.EXTRA,
        DiffKind.CHANGED,
    )

    def __post_init__(self) -> None:
        self._counts = Counter()
        self._kind_buckets: dict[DiffKind, list[DiffEntry]] = {kind: [] for kind in DiffKind}
        self._variable_counts = Counter()
        self._top_variables_cache = None
        self._variables_by_kind_cache = None
        self._sorted_kind_cache = {}
        self._variables_cache = None
        self._sorted_entries_cache = None
        self._counts_by_kind_mapping = None
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

    def _invalidate_entry_caches(self, entry: DiffEntry) -> None:
        self._top_variables_cache = None
        self._variables_by_kind_cache = None
        self._sorted_kind_cache.pop(entry.kind, None)
        self._variables_cache = None
        self._sorted_entries_cache = None
        self._counts_by_kind_mapping = None

    def _track_entry(self, entry: DiffEntry) -> None:
        self._counts[entry.kind] += 1
        self._kind_buckets.setdefault(entry.kind, []).append(entry)
        self._variable_counts[entry.variable] += 1
        self._invalidate_entry_caches(entry)

    def add(self, entry: DiffEntry) -> None:
        self.entries.append(entry)
        self._track_entry(entry)

    def to_dict(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = normalized_limit(top_limit)
        return {
            "change_count": self.change_count,
            "is_clean": self.is_clean(),
            "by_kind": dict(self.counts_by_kind()),
            "entries": [entry.to_dict() for entry in self.entries],
            "variables": list(self.variables()),
            "top_variables": self.top_variables(limit),
            "variables_by_kind": self.variables_by_kind(),
            "non_empty_kinds": [kind.value for kind in self.non_empty_kinds()],
        }

    def sorted_entries(self) -> list[DiffEntry]:
        cached = self._sorted_entries_cache
        if cached is not None:
            return [*cached]
        order = {kind: index for index, kind in enumerate(self._kind_order)}
        sorted_entries = tuple(
            sorted(
                self.entries,
                key=lambda item: (
                    order[item.kind],
                    item.variable.casefold(),
                    item.variable,
                ),
            )
        )
        self._sorted_entries_cache = sorted_entries
        return [*sorted_entries]

    def entries_by_kind(self, kind: DiffKind) -> list[DiffEntry]:
        cached = self._sorted_kind_cache.get(kind)
        if cached is not None:
            return [*cached]
        bucket = self._kind_buckets.get(kind)
        if not bucket:
            self._sorted_kind_cache[kind] = ()
            return []
        sorted_bucket = tuple(
            sorted(
                bucket,
                key=lambda item: (item.variable.casefold(), item.variable),
            )
        )
        self._sorted_kind_cache[kind] = sorted_bucket
        return [*sorted_bucket]

    def count_for(self, kind: DiffKind) -> int:
        return self._counts.get(kind, 0)

    def has_kind(self, kind: DiffKind) -> bool:
        return self.count_for(kind) > 0

    def non_empty_kinds(self) -> tuple[DiffKind, ...]:
        return tuple(kind for kind in self._kind_order if self.has_kind(kind))

    def variables(self) -> tuple[str, ...]:
        cached = self._variables_cache
        if cached is not None:
            return cached
        if not self._variable_counts:
            self._variables_cache = ()
            return ()
        computed = tuple(
            sorted(
                self._variable_counts,
                key=lambda name: (name.casefold(), name),
            )
        )
        self._variables_cache = computed
        return computed

    def has_variable(self, variable: str) -> bool:
        return variable in self._variable_counts

    def top_variables(self, limit: int | None = None) -> Sequence[tuple[str, int]]:
        if self._top_variables_cache is None:
            self._top_variables_cache = tuple(
                sorted(
                    self._variable_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            )
        if limit is None:
            return list(self._top_variables_cache)
        if limit == 0:
            return []
        return list(self._top_variables_cache[:limit])

    def variables_by_kind(self) -> dict[str, list[str]]:
        if self._variables_by_kind_cache is None:
            computed: dict[str, tuple[str, ...]] = {}
            for kind in DiffKind:
                variables = {
                    entry.variable
                    for entry in self._kind_buckets.get(kind, [])
                }
                computed[kind.value] = tuple(
                    sorted(
                        variables,
                        key=lambda name: (name.casefold(), name),
                    )
                )
            self._variables_by_kind_cache = computed
        return {
            key: list(values)
            for key, values in self._variables_by_kind_cache.items()
        }

    def counts_by_kind(self) -> Mapping[str, int]:
        if self._counts_by_kind_mapping is None:
            data = {
                kind.value: self.count_for(kind)
                for kind in self._kind_order
            }
            self._counts_by_kind_mapping = MappingProxyType(data)
        return self._counts_by_kind_mapping

    def summary(self, *, top_limit: int | None = None) -> dict[str, Any]:
        limit = normalized_limit(top_limit)
        return {
            "change_count": self.change_count,
            "is_clean": self.is_clean(),
            "by_kind": dict(self.counts_by_kind()),
            "non_empty_kinds": [kind.value for kind in self.non_empty_kinds()],
            "variables": list(self.variables()),
            "top_variables": self.top_variables(limit),
            "variables_by_kind": self.variables_by_kind(),
        }


def _redact(value: str | None) -> str | None:
    if value is None:
        return None
    return "***"
