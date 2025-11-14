from __future__ import annotations

import logging
from importlib.metadata import entry_points
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class Backend(Protocol):
    """
    Protocol for a secrets backend plugin.

    A backend is responsible for fetching values from a remote source
    based on a list of source URIs defined in the envkeep spec.
    """

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        """
        Fetch values from the backend.

        Args:
            sources: A dictionary mapping variable names to their source URIs.

        Returns:
            A dictionary mapping the variable name to its fetched value.
            The key should be the variable name as it appears in the spec.
        """
        ...  # pragma: no cover


def load_backends() -> dict[str, Backend]:
    """Discover and load all installed backend plugins."""
    backends: dict[str, Backend] = {}
    for entry_point in entry_points(group="envkeep.backends"):
        try:
            backend_instance = entry_point.load()()
            if isinstance(backend_instance, Backend) and callable(
                getattr(backend_instance, "fetch", None),
            ):
                backends[entry_point.name] = backend_instance
        except Exception:
            logger.exception("Failed to load plugin: %s", entry_point.name)
    return backends


def load_validator(name: str) -> callable | None:
    """Discover and load a custom validator function."""
    for entry_point in entry_points(group="envkeep.validators"):
        if entry_point.name == name:
            try:
                return entry_point.load()
            except Exception:
                logger.exception("Failed to load validator: %s", entry_point.name)
    return None
