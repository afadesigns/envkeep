"""Envkeep public API."""

from importlib import metadata

__version__ = metadata.version("envkeep")

from .report import (
    DiffEntry,
    DiffKind,
    DiffReport,
    IssueSeverity,
    ValidationIssue,
    ValidationReport,
)
from .snapshot import EnvSnapshot
from .spec import EnvSpec, ProfileSpec, VariableSpec, VariableType

__all__ = [
    "DiffKind",
    "EnvSpec",
    "EnvSnapshot",
    "VariableSpec",
    "VariableType",
    "ProfileSpec",
    "ValidationIssue",
    "ValidationReport",
    "IssueSeverity",
    "DiffEntry",
    "DiffReport",
    "__version__",
]
