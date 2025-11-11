from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from . import __version__
from .report import ValidationReport

logger = logging.getLogger(__name__)


def _hash_file(path: Path) -> str:
    """Return the SHA256 hash of a file's content."""
    hasher = hashlib.sha256()
    hasher.update(path.read_bytes())
    return hasher.hexdigest()


class Cache:
    """Manages the caching of validation reports."""

    def __init__(self, cache_dir: Path | str = ".envkeep_cache"):
        self._root = Path(cache_dir)
        self._spec_hash_file = self._root / "spec.hash"

    def _ensure_dir(self) -> None:
        self._root.mkdir(exist_ok=True)

    def get_report(self, profile_path: Path, spec_path: Path) -> ValidationReport | None:
        """
        Retrieve a cached report if the spec and profile file are unchanged.
        """
        if not self._root.exists():
            return None

        try:
            cached_spec_hash = self._spec_hash_file.read_text(encoding="utf-8")
            current_spec_hash = f"{_hash_file(spec_path)}:{__version__}"
            if cached_spec_hash != current_spec_hash:
                return None  # Spec has changed, cache is invalid

            profile_cache_file = self._root / f"{_hash_file(profile_path)}.json"
            if not profile_cache_file.exists():
                return None

            data = json.loads(profile_cache_file.read_text(encoding="utf-8"))
            return ValidationReport.from_dict(data)
        except FileNotFoundError:
            return None  # Cache directory or spec hash file not found
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to read cache: %s", e)
            return None

    def set_report(self, profile_path: Path, spec_path: Path, report: ValidationReport) -> None:
        """Cache a validation report."""
        self._ensure_dir()
        try:
            current_spec_hash = f"{_hash_file(spec_path)}:{__version__}"
            self._spec_hash_file.write_text(current_spec_hash, encoding="utf-8")

            profile_cache_file = self._root / f"{_hash_file(profile_path)}.json"
            profile_cache_file.write_text(json.dumps(report.to_dict()), encoding="utf-8")
        except OSError as e:
            # If caching fails, it's not a critical error.
            logger.warning("Failed to write cache: %s", e)
            pass
