# Plugin Development Guide

Envkeep's plugin system allows you to create custom backends for fetching variables from any remote source, such as cloud secret managers, configuration databases, or internal APIs.

## The Backend Protocol

A backend is a Python class that implements the `Backend` protocol defined in `envkeep.plugins`. It must have a single method, `fetch`, which takes a dictionary of variable names to source URIs and returns a dictionary of fetched variable names to their values.

```python
from __future__ import annotations
from typing import Protocol

class Backend(Protocol):
    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        ...
```

## Example: JSON File Backend

Here is a simple example of a backend that fetches values from a JSON file.

```python
# src/envkeep_json/backend.py
import json
from pathlib import Path

class JsonBackend:
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
            except Exception:
                # It's good practice to handle errors gracefully
                pass
        return fetched_values
```

## Registering Your Plugin

To make your backend discoverable by Envkeep, you must register it as an entry point in your package's `pyproject.toml` (or `setup.cfg`). The entry point group is `envkeep.backends`.

```toml
[project.entry-points."envkeep.backends"]
json = "envkeep_json.backend:JsonBackend"
```

In this example, `json` is the name of the backend that users will reference in the `source` URI (e.g., `source = "json:..."`). The value is the import path to your backend class.

## Usage in `envkeep.toml`

Once a plugin is installed, users can reference it in their `envkeep.toml` file:

```toml
[[variables]]
name = "API_KEY"
type = "string"
secret = true
source = "json:/path/to/secrets.json#api_key"
```

When `envkeep check` is run, it will:
1. Discover the `json` backend via its entry point.
2. Instantiate the `JsonBackend` class.
3. Call the `fetch` method with `{"API_KEY": "/path/to/secrets.json#api_key"}`.
4. Use the returned value for validation.
