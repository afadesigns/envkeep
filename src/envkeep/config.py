from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._compat import tomllib


@dataclass(slots=True)
class Config:
    """Represents envkeep configuration loaded from pyproject.toml."""

    spec_path: Path | None = None
    profile_base: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_root: Path) -> Config:
        """Create a Config instance from a dictionary."""
        spec_path_str = data.get("spec")
        profile_base_str = data.get("profile_base")

        spec_path = (project_root / spec_path_str).resolve() if spec_path_str else None
        profile_base = (project_root / profile_base_str).resolve() if profile_base_str else None

        return cls(spec_path=spec_path, profile_base=profile_base)


def find_pyproject_toml(start_dir: Path | None = None) -> Path | None:
    """Find the pyproject.toml file by searching upwards from the start directory."""
    current_dir = start_dir or Path.cwd()
    while current_dir != current_dir.parent:
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            return pyproject_path
        current_dir = current_dir.parent
    return None


def load_config() -> Config:
    """Load envkeep configuration from pyproject.toml."""
    pyproject_path = find_pyproject_toml()
    if not pyproject_path:
        return Config()

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        envkeep_config = data.get("tool", {}).get("envkeep", {})
        project_root = pyproject_path.parent
        return Config.from_dict(envkeep_config, project_root)
    except (OSError, tomllib.TOMLDecodeError):
        return Config()
