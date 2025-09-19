from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_ENV_LINE_RE = re.compile(r"^(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.*)$")


@dataclass(slots=True)
class EnvSnapshot:
    """Represents a concrete set of environment variables."""

    values: dict[str, str]
    source: str
    duplicates: tuple[str, ...] = ()
    invalid_lines: tuple[tuple[int, str], ...] = ()

    @classmethod
    def from_mapping(
        cls,
        mapping: dict[str, str],
        *,
        source: str = "mapping",
        duplicates: Iterable[str] | None = None,
        invalid_lines: Iterable[tuple[int, str]] | None = None,
    ) -> "EnvSnapshot":
        return cls(
            values=dict(mapping),
            source=source,
            duplicates=tuple(duplicates or ()),
            invalid_lines=tuple(invalid_lines or ()),
        )

    @classmethod
    def from_process(cls) -> "EnvSnapshot":
        return cls.from_mapping(dict(os.environ), source="process")

    @classmethod
    def from_env_file(cls, path: str | Path) -> "EnvSnapshot":
        path_obj = Path(path)
        content = path_obj.read_text(encoding="utf-8")
        values, duplicates, invalid_lines = _parse_env(content)
        return cls(
            values=values,
            source=str(path_obj),
            duplicates=duplicates,
            invalid_lines=invalid_lines,
        )

    @classmethod
    def from_text(cls, raw: str, *, source: str = "<inline>") -> "EnvSnapshot":
        values, duplicates, invalid_lines = _parse_env(raw)
        return cls(
            values=values,
            source=source,
            duplicates=duplicates,
            invalid_lines=invalid_lines,
        )

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def keys(self) -> Iterable[str]:
        return self.values.keys()

    def items(self) -> Iterable[tuple[str, str]]:
        return self.values.items()

    def duplicate_keys(self) -> tuple[str, ...]:
        """Return keys that were declared multiple times in the source."""

        if not self.duplicates:
            return ()
        # Preserve discovery order while removing repeated duplicates
        seen: set[str] = set()
        ordered: list[str] = []
        for key in self.duplicates:
            if key not in seen:
                seen.add(key)
                ordered.append(key)
        return tuple(ordered)

    def malformed_lines(self) -> tuple[tuple[int, str], ...]:
        """Return non-empty lines that could not be parsed."""

        return self.invalid_lines

    def __contains__(self, key: str) -> bool:  # pragma: no cover
        return key in self.values


def _parse_env(raw: str) -> tuple[dict[str, str], tuple[str, ...], tuple[tuple[int, str], ...]]:
    result: dict[str, str] = {}
    duplicates: list[str] = []
    invalid: list[tuple[int, str]] = []
    for index, line in enumerate(raw.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(stripped)
        if not match:
            invalid.append((index, line.rstrip("\n")))
            continue
        key = match.group("key")
        value = match.group("value")
        processed = _sanitize_value(value)
        if key in result:
            duplicates.append(key)
        result[key] = _unescape(processed)
    return result, tuple(duplicates), tuple(invalid)


def _sanitize_value(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if trimmed[0] in {'"', "'"}:
        quote = trimmed[0]
        idx = 1
        buffer: list[str] = []
        while idx < len(trimmed):
            char = trimmed[idx]
            if char == "\\":
                # Preserve escape sequences so downstream unescape keeps semantics.
                if idx + 1 < len(trimmed):
                    buffer.append(trimmed[idx : idx + 2])
                    idx += 2
                    continue
                buffer.append("\\")
                idx += 1
                continue
            if char == quote:
                idx += 1
                break
            buffer.append(char)
            idx += 1
        remainder = trimmed[idx:].strip()
        if remainder and not remainder.startswith("#"):
            remainder = _strip_inline_comment(remainder)
            if remainder:
                buffer.append(" ")
                buffer.append(remainder)
        return "".join(buffer)
    return _strip_inline_comment(trimmed)


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    for idx, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return value[:idx].rstrip()
    return value


def _unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace("\\t", "\t")
