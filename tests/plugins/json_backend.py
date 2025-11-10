from __future__ import annotations

import json
from pathlib import Path

from envkeep.plugins import Backend


class JsonBackend(Backend):
    """A simple backend that reads values from a JSON file."""

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        fetched_values: dict[str, str] = {}
        for var_name, source_uri in sources.items():
            try:
                file_path_str, key = source_uri.split("#", 1)
                file_path = Path(file_path_str)
                if file_path.exists():
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    value = data.get(key)
                    if value is not None:
                        fetched_values[var_name] = str(value)
            except (ValueError, FileNotFoundError, json.JSONDecodeError):
                # Ignore errors in the test plugin
                pass
        return fetched_values
