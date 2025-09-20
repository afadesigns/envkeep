from __future__ import annotations

try:  # pragma: no cover - runtime compatibility shim
    import tomllib as _tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    import tomli as _tomllib  # type: ignore[import-not-found]

# Re-export for modules that need a tomllib-compatible loader.
tomllib = _tomllib

__all__ = ["tomllib"]
