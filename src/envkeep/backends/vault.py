from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..plugins import Backend

if TYPE_CHECKING:
    from hvac import Client

logger = logging.getLogger(__name__)


class VaultBackend(Backend):
    """Fetch secrets from HashiCorp Vault."""

    def __init__(self) -> None:
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            try:
                import hvac
            except ImportError as exc:
                raise ImportError(
                    "hvac is not installed. Run `pip install envkeep[vault]`.",
                ) from exc
            self._client = hvac.Client()
        return self._client

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        client = self._get_client()
        results: dict[str, str] = {}
        for name, path in sources.items():
            try:
                # Assuming KVv2, which is common. The path is split into mount_point and secret_path
                parts = path.split("/", 1)
                mount_point = parts[0]
                secret_path = parts[1] if len(parts) > 1 else ""

                response = client.secrets.kv.v2.read_secret_version(
                    path=secret_path,
                    mount_point=mount_point,
                )
                # The secret value is in response['data']['data']
                secret_data = response.get("data", {}).get("data", {})
                if isinstance(secret_data, dict):
                    # For simplicity, this backend will return the value of the
                    # *first* key found in the secret. A more advanced
                    # implementation could allow specifying the key in the
                    # source string.
                    if secret_data:
                        first_key = next(iter(secret_data))
                        results[name] = secret_data[first_key]
            except Exception:
                logger.exception("Failed to fetch secret: %s", path)
        return results