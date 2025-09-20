"""Pytest configuration for Envkeep tests."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    """Prepend the project src directory so tests import envkeep reliably."""

    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    src_str = str(src_path)
    if src_path.is_dir() and src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()

