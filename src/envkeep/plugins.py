from __future__ import annotations

from importlib.metadata import entry_points
from typing import Protocol


class Backend(Protocol):
    """
    Protocol for a secrets backend plugin.

    A backend is responsible for fetching values from a remote source
    based on a list of source URIs defined in the envkeep spec.
    """

    def fetch(self, sources: list[str]) -> dict[str, str]:
        """
        Fetch values from the backend.

        Args:
            sources: A list of source URIs specific to this backend.
                     The prefix (e.g., "vault:") will be stripped.

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
            if callable(getattr(backend_instance, "fetch", None)):
                backends[entry_point.name] = backend_instance
        except Exception:
            # Ignore plugins that fail to load
            pass
    return backends
