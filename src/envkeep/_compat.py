from __future__ import annotations

from importlib import import_module
from types import ModuleType

try:  # pragma: no cover - prefer stdlib tomllib when available
    tomllib: ModuleType = import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    tomllib = import_module("tomli")

__all__ = ["tomllib"]
