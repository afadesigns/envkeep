from __future__ import annotations

# Shared helper utilities for envkeep modules.
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

import typer

BOM = "\ufeff"

if TYPE_CHECKING:  # pragma: no cover - typing shim for Typer runtime compatibility
    OptionalPath = Path | None
else:  # pragma: no cover - Typer inspects runtime annotations
    OptionalPath = Path


def normalized_limit(limit: int | None) -> int | None:
    """Clamp negative summary limits to zero while preserving ``None``."""

    if limit is None:
        return None
    return max(limit, 0)


def casefold_sorted(values: Iterable[str]) -> list[str]:
    """Return values sorted deterministically with casefold ordering."""

    return sorted(values, key=lambda item: (item.casefold(), item))


def sorted_counter(counter: Counter[str]) -> list[tuple[str, int]]:
    """Return counter contents sorted by frequency (desc) then name."""

    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def resolve_optional_path_option(
    value: OptionalPath | str | typer.models.OptionInfo | None,
) -> Path | None:
    """Convert Typer option placeholders into a usable optional ``Path``."""

    if isinstance(value, typer.models.OptionInfo) or value is None:
        return None
    if isinstance(value, Path):
        return value
    return Path(value)


def strip_bom(text: str) -> str:
    """Remove a UTF-8 BOM prefix if present."""

    if text.startswith(BOM):
        return text[len(BOM) :]
    return text


def line_number_sort_key(value: str) -> tuple[int, str]:
    """Return a sortable key that prefers embedded digits when present."""

    digits = "".join(char for char in value if char.isdigit())
    number = int(digits) if digits else 0
    return number, value


__all__ = [
    "BOM",
    "OptionalPath",
    "casefold_sorted",
    "normalized_limit",
    "line_number_sort_key",
    "resolve_optional_path_option",
    "sorted_counter",
    "strip_bom",
]
