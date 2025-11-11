from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlparse

from ._compat import tomllib
from .report import (
    DiffEntry,
    DiffKind,
    DiffReport,
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
)
from .snapshot import EnvSnapshot
from .utils import casefold_sorted


def _assert_unique(values: Iterable[str], *, entity: str) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen:
            duplicates.append(value)
        else:
            seen.add(value)
    if duplicates:
        joined = ", ".join(dict.fromkeys(duplicates))
        raise ValueError(f"duplicate {entity} declared: {joined}")


_BOOL_TRUE = {"1", "true", "on", "yes"}
_BOOL_FALSE = {"0", "false", "off", "no"}


class VariableType(str, Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    URL = "url"
    PATH = "path"
    JSON = "json"
    LIST = "list"

    def normalize(self, raw: str) -> str:
        raw = raw.strip()
        if self is VariableType.STRING:
            return raw
        if self is VariableType.INT:
            return str(int(raw, 10))
        if self is VariableType.FLOAT:
            return format(float(raw), ".6g")
        if self is VariableType.BOOL:
            lowered = raw.lower()
            if lowered in _BOOL_TRUE:
                return "true"
            if lowered in _BOOL_FALSE:
                return "false"
            raise ValueError("invalid boolean value")
        if self is VariableType.URL:
            parsed = urlparse(raw)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("invalid URL")
            return parsed.geturl()
        if self is VariableType.PATH:
            return str(Path(raw).as_posix())
        if self is VariableType.JSON:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - explicit message
                raise ValueError(f"invalid JSON: {exc.msg}") from exc
            return json.dumps(data, sort_keys=True)
        if self is VariableType.LIST:
            items = [item.strip() for item in raw.split(",") if item.strip()]
            return ",".join(items)
        raise ValueError(f"unsupported type: {self.value}")

    def default_example(self) -> str:
        if self is VariableType.STRING:
            return "value"
        if self is VariableType.INT:
            return "42"
        if self is VariableType.FLOAT:
            return "3.14"
        if self is VariableType.BOOL:
            return "true"
        if self is VariableType.URL:
            return "https://example.com"
        if self is VariableType.PATH:
            return "/var/app/data"
        if self is VariableType.JSON:
            return '{"key": "value"}'
        if self is VariableType.LIST:
            return "value1,value2"
        raise ValueError(f"unhandled variable type: {self.value}")


@dataclass(slots=True)
class VariableSpec:
    name: str
    var_type: VariableType
    required: bool = True
    default: str | None = None
    description: str | None = None
    secret: bool = False
    choices: tuple[str, ...] = ()
    pattern: re.Pattern[str] | None = None
    example: str | None = None
    allow_empty: bool = False
    source: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariableSpec:
        name = data["name"]
        var_type = VariableType(data.get("type", "string"))
        pattern_value = data.get("pattern")
        compiled = re.compile(pattern_value) if pattern_value else None
        choices = tuple(str(choice) for choice in data.get("choices", []))
        default = data.get("default")
        if default is not None:
            default = str(default)
        example = data.get("example")
        if example is not None:
            example = str(example)
        instance = cls(
            name=name,
            var_type=var_type,
            required=bool(data.get("required", True)),
            default=default,
            description=data.get("description"),
            secret=bool(data.get("secret", False)),
            choices=choices,
            pattern=compiled,
            example=example,
            allow_empty=bool(data.get("allow_empty", False)),
            source=data.get("source"),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
        )
        if default is not None:
            instance.validate(default)
        return instance

    def _validate_not_empty(self, value: str) -> None:
        if not value and not self.allow_empty:
            raise ValueError("value may not be empty")

    def _validate_choices(self, normalized: str) -> None:
        if self.choices and normalized not in self.choices:
            raise ValueError(f"value must be one of {self.choices}")

    def _validate_pattern(self, normalized: str) -> None:
        if self.pattern and not self.pattern.fullmatch(normalized):
            raise ValueError("value does not match pattern")

    def _validate_length(self, normalized: str) -> None:
        if self.min_length is not None and len(normalized) < self.min_length:
            raise ValueError(f"length must be at least {self.min_length}")
        if self.max_length is not None and len(normalized) > self.max_length:
            raise ValueError(f"length must be at most {self.max_length}")

    def _validate_value_range(self, normalized: str) -> None:
        if self.min_value is not None:
            if self.var_type in (VariableType.INT, VariableType.FLOAT):
                if float(normalized) < self.min_value:
                    raise ValueError(f"value must be at least {self.min_value}")
        if self.max_value is not None:
            if self.var_type in (VariableType.INT, VariableType.FLOAT):
                if float(normalized) > self.max_value:
                    raise ValueError(f"value must be at most {self.max_value}")

    def validate(self, value: str) -> str:
        self._validate_not_empty(value)
        normalized = self.var_type.normalize(value)
        self._validate_choices(normalized)
        self._validate_pattern(normalized)
        self._validate_length(normalized)
        self._validate_value_range(normalized)
        return normalized

    def normalize(self, value: str) -> str:
        return self.validate(value)

    def sample(self) -> str:
        if self.default is not None:
            return self.default
        if self.example is not None:
            return self.example
        if self.secret:
            return "<redacted>"
        return self.var_type.default_example()


@dataclass(slots=True)
class ProfileSpec:
    name: str
    env_file: str
    description: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileSpec:
        return cls(
            name=data["name"],
            env_file=data["env_file"],
            description=data.get("description"),
        )


@dataclass(slots=True)
class EnvSpec:
    version: int
    variables: list[VariableSpec]
    profiles: list[ProfileSpec] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _variable_cache: Mapping[str, VariableSpec] = field(init=False, repr=False)
    _profile_cache: Mapping[str, ProfileSpec] = field(init=False, repr=False)
    _variable_names: tuple[str, ...] = field(init=False, repr=False)
    _profile_names: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_caches()

    @classmethod
    def from_file(cls, path: str | Path) -> EnvSpec:
        path_obj = Path(path)
        data = tomllib.loads(path_obj.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvSpec:
        version = int(data.get("version", 1))
        metadata = data.get("metadata", {})
        variables_data = data.get("variables", [])
        profiles_data = data.get("profiles", [])
        variables = [VariableSpec.from_dict(item) for item in variables_data]
        _assert_unique([var.name for var in variables], entity="variable")
        profiles = [ProfileSpec.from_dict(item) for item in profiles_data]
        _assert_unique([profile.name for profile in profiles], entity="profile")
        return cls(version=version, variables=variables, profiles=profiles, metadata=dict(metadata))

    def variable_map(self) -> Mapping[str, VariableSpec]:
        return self._variable_cache

    def _validate_variables(self, snapshot: EnvSnapshot, report: ValidationReport) -> None:
        """Validate variables against the spec."""
        variables = self.variable_map()
        for name, spec in variables.items():
            raw = snapshot.get(name)
            if raw is None:
                if spec.default is not None or not spec.required:
                    continue
                report.add(
                    ValidationIssue(
                        variable=name,
                        message="missing required variable",
                        severity=IssueSeverity.ERROR,
                        code="missing",
                        hint="Declare it in the environment or provide a default.",
                    ),
                )
                continue
            try:
                spec.validate(raw)
            except ValueError as exc:
                report.add(
                    ValidationIssue(
                        variable=name,
                        message=str(exc),
                        severity=IssueSeverity.ERROR,
                        code="invalid",
                    ),
                )

    def _check_for_extra_variables(
        self,
        snapshot: EnvSnapshot,
        report: ValidationReport,
        allow_extra: bool,
    ) -> None:
        """Check for variables not declared in the spec."""
        if not allow_extra:
            extras = [key for key in snapshot.keys() if key not in self.variable_map()]
            for key in casefold_sorted(extras):
                report.add(
                    ValidationIssue(
                        variable=key,
                        message="variable not declared in spec",
                        severity=IssueSeverity.WARNING,
                        code="extra",
                        hint="Add it to envkeep.toml or remove it from the environment.",
                    ),
                )

    def _check_for_duplicate_keys(self, snapshot: EnvSnapshot, report: ValidationReport) -> None:
        """Check for duplicate keys in the snapshot."""
        for key in snapshot.duplicate_keys():
            report.add(
                ValidationIssue(
                    variable=key,
                    message="variable declared multiple times",
                    severity=IssueSeverity.WARNING,
                    code="duplicate",
                    hint="Remove duplicate assignments to keep configuration deterministic.",
                ),
            )

    def _check_for_invalid_lines(self, snapshot: EnvSnapshot, report: ValidationReport) -> None:
        """Check for invalid lines in the snapshot."""
        for line_no, raw in snapshot.malformed_lines():
            report.add(
                ValidationIssue(
                    variable=f"line {line_no}",
                    message="line could not be parsed",
                    severity=IssueSeverity.WARNING,
                    code="invalid_line",
                    hint=f"Review the syntax: {raw}",
                ),
            )

    def validate(self, snapshot: EnvSnapshot, *, allow_extra: bool = False) -> ValidationReport:
        report = ValidationReport()
        self._validate_variables(snapshot, report)
        self._check_for_extra_variables(snapshot, report, allow_extra)
        self._check_for_duplicate_keys(snapshot, report)
        self._check_for_invalid_lines(snapshot, report)
        return report

    def _compare_variables(
        self,
        left: EnvSnapshot,
        right: EnvSnapshot,
        report: DiffReport,
    ) -> None:
        """Compare variables between two snapshots."""
        variables = self.variable_map()
        for name, spec in variables.items():
            left_val = left.get(name)
            right_val = right.get(name)
            if left_val is None and right_val is None:
                continue
            if left_val is None:
                if right_val is None:
                    continue
                report.add(
                    DiffEntry(
                        variable=name,
                        kind=DiffKind.EXTRA,
                        left=None,
                        right=spec.normalize(right_val),
                        secret=spec.secret,
                    ),
                )
                continue
            if right_val is None:
                report.add(
                    DiffEntry(
                        variable=name,
                        kind=DiffKind.MISSING,
                        left=spec.normalize(left_val),
                        right=None,
                        secret=spec.secret,
                    ),
                )
                continue
            try:
                left_normalized = spec.normalize(left_val)
                right_normalized = spec.normalize(right_val)
            except ValueError:
                # Treat normalization errors as changes without exposing raw secret material.
                report.add(
                    DiffEntry(
                        variable=name,
                        kind=DiffKind.CHANGED,
                        left=left_val,
                        right=right_val,
                        secret=spec.secret,
                    ),
                )
                continue
            if left_normalized != right_normalized:
                report.add(
                    DiffEntry(
                        variable=name,
                        kind=DiffKind.CHANGED,
                        left=left_normalized,
                        right=right_normalized,
                        secret=spec.secret,
                    ),
                )

    def _handle_extra_variables(
        self,
        left: EnvSnapshot,
        right: EnvSnapshot,
        report: DiffReport,
    ) -> None:
        """Handle extra variables in both snapshots."""
        variables = self.variable_map()
        left_extra = set(left.keys()) - variables.keys()
        right_extra = set(right.keys()) - variables.keys()
        for key in casefold_sorted(left_extra):
            report.add(
                DiffEntry(
                    variable=key,
                    kind=DiffKind.MISSING,
                    left=left.get(key),
                    right=None,
                    secret=False,
                ),
            )
        for key in casefold_sorted(right_extra):
            report.add(
                DiffEntry(
                    variable=key,
                    kind=DiffKind.EXTRA,
                    left=None,
                    right=right.get(key),
                    secret=False,
                ),
            )

    def diff(self, left: EnvSnapshot, right: EnvSnapshot) -> DiffReport:
        report = DiffReport()
        self._compare_variables(left, right, report)
        self._handle_extra_variables(left, right, report)
        return report

    def generate_example(self, *, redact_secrets: bool = True) -> str:
        lines: list[str] = []
        for spec in self.variables:
            sample = spec.sample()
            if redact_secrets and spec.secret:
                sample = "***"
            comment = f"# {spec.description}" if spec.description else None
            if comment:
                lines.append(comment)
            lines.append(f"{spec.name}={sample}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def profiles_by_name(self) -> Mapping[str, ProfileSpec]:
        return self._profile_cache

    def iter_profiles(self) -> Iterable[ProfileSpec]:
        return iter(self.profiles)

    def summary(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "metadata": self.metadata,
            "variables": list(self.variable_names()),
            "profiles": list(self.profile_names()),
        }

    def _rebuild_caches(self) -> None:
        self._variable_cache = MappingProxyType(
            {variable.name: variable for variable in self.variables},
        )
        self._profile_cache = MappingProxyType({profile.name: profile for profile in self.profiles})
        self._variable_names = tuple(variable.name for variable in self.variables)
        self._profile_names = tuple(profile.name for profile in self.profiles)

    def variable_names(self) -> tuple[str, ...]:
        return self._variable_names

    def profile_names(self) -> tuple[str, ...]:
        return self._profile_names
