from __future__ import annotations

from collections import Counter
from pathlib import Path

import typer

from envkeep.utils import (
    casefold_sorted,
    normalized_limit,
    resolve_optional_path_option,
    sorted_counter,
    strip_bom,
)


def test_normalized_limit_behaviour() -> None:
    assert normalized_limit(None) is None
    assert normalized_limit(-5) == 0
    assert normalized_limit(7) == 7


def test_casefold_sorted_deterministic() -> None:
    values = ["Bravo", "alpha", "Alpha"]
    assert casefold_sorted(values) == ["Alpha", "alpha", "Bravo"]


def test_sorted_counter_orders_by_frequency() -> None:
    counter = Counter({"dup": 3, "other": 1, "Dup": 3})
    assert sorted_counter(counter) == [("Dup", 3), ("dup", 3), ("other", 1)]


def test_strip_bom_removes_prefix() -> None:
    assert strip_bom("\ufeffvalue") == "value"
    assert strip_bom("value") == "value"


def test_resolve_optional_path_option_handles_placeholders(tmp_path: Path) -> None:
    option_placeholder = typer.Option(None)
    assert resolve_optional_path_option(option_placeholder) is None

    path = tmp_path / "config.env"
    assert resolve_optional_path_option(path) == path
    assert resolve_optional_path_option(None) is None


def test_resolve_optional_path_option_accepts_strings(tmp_path: Path) -> None:
    path = tmp_path / "config.env"
    resolved = resolve_optional_path_option(str(path))
    assert resolved == path
    assert isinstance(resolved, Path)
