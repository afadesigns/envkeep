from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from urllib.parse import urlparse

from ._compat import tomllib

from .report import DiffEntry, DiffKind, DiffReport, IssueSeverity, ValidationIssue, ValidationReport
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
        return "value"


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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VariableSpec":
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
        )
        if default is not None:
            instance.validate(default)
        return instance

    def validate(self, value: str) -> str:
        if not value and not self.allow_empty:
            raise ValueError("value may not be empty")
        normalized = self.var_type.normalize(value)
        if self.choices and normalized not in self.choices:
            raise ValueError(f"value must be one of {self.choices}")
        if self.pattern and not self.pattern.fullmatch(normalized):
            raise ValueError("value does not match pattern")
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
    def from_dict(cls, data: dict[str, Any]) -> "ProfileSpec":
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
    def from_file(cls, path: str | Path) -> "EnvSpec":
        path_obj = Path(path)
        data = tomllib.loads(path_obj.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvSpec":
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

    def validate(self, snapshot: EnvSnapshot, *, allow_extra: bool = False) -> ValidationReport:
        report = ValidationReport()
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
                    )
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
                    )
                )
        if not allow_extra:
            extras = [key for key in snapshot.keys() if key not in variables]
            for key in casefold_sorted(extras):
                report.add(
                    ValidationIssue(
                        variable=key,
                        message="variable not declared in spec",
                        severity=IssueSeverity.WARNING,
                        code="extra",
                        hint="Add it to envkeep.toml or remove it from the environment.",
                    )
                )
        for key in snapshot.duplicate_keys():
            report.add(
                ValidationIssue(
                    variable=key,
                    message="variable declared multiple times",
                    severity=IssueSeverity.WARNING,
                    code="duplicate",
                    hint="Remove duplicate assignments to keep configuration deterministic.",
                )
            )
        for line_no, raw in snapshot.malformed_lines():
            report.add(
                ValidationIssue(
                    variable=f"line {line_no}",
                    message="line could not be parsed",
                    severity=IssueSeverity.WARNING,
                    code="invalid_line",
                    hint=f"Review the syntax: {raw}",
                )
            )
        return report

    def diff(self, left: EnvSnapshot, right: EnvSnapshot) -> DiffReport:
        report = DiffReport()
        variables = self.variable_map()
        for name, spec in variables.items():
            left_val = left.get(name)
            right_val = right.get(name)
            if left_val is None and right_val is None:
                continue
            if left_val is None and right_val is not None:
                report.add(DiffEntry(variable=name, kind=DiffKind.EXTRA, left=None, right=spec.normalize(right_val), secret=spec.secret))
                continue
            if left_val is not None and right_val is None:
                report.add(DiffEntry(variable=name, kind=DiffKind.MISSING, left=spec.normalize(left_val), right=None, secret=spec.secret))
                continue
            assert left_val is not None and right_val is not None
            try:
                left_normalized = spec.normalize(left_val)
                right_normalized = spec.normalize(right_val)
            except ValueError:
                # Treat normalization errors as changed values without exposing raw data for secrets.
                report.add(DiffEntry(variable=name, kind=DiffKind.CHANGED, left=left_val, right=right_val, secret=spec.secret))
                continue
            if left_normalized != right_normalized:
                report.add(
                    DiffEntry(
                        variable=name,
                        kind=DiffKind.CHANGED,
                        left=left_normalized,
                        right=right_normalized,
                        secret=spec.secret,
                    )
                )
        left_extra = set(left.keys()) - variables.keys()
        right_extra = set(right.keys()) - variables.keys()
        for key in casefold_sorted(left_extra):
            report.add(DiffEntry(variable=key, kind=DiffKind.MISSING, left=left.get(key), right=None, secret=False))
        for key in casefold_sorted(right_extra):
            report.add(DiffEntry(variable=key, kind=DiffKind.EXTRA, left=None, right=right.get(key), secret=False))
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
        self._variable_cache = MappingProxyType({variable.name: variable for variable in self.variables})
        self._profile_cache = MappingProxyType({profile.name: profile for profile in self.profiles})
        self._variable_names = tuple(variable.name for variable in self.variables)
        self._profile_names = tuple(profile.name for profile in self.profiles)

    def variable_names(self) -> tuple[str, ...]:
        return self._variable_names

    def profile_names(self) -> tuple[str, ...]:
        return self._profile_names
