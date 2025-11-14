from __future__ import annotations

import os
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from envkeep.plugins import Backend


class AzureKeyVaultBackend(Backend):
    """A secrets backend for Azure Key Vault."""

    def __init__(self) -> None:
        self.clients: dict[str, SecretClient] = {}

    @lru_cache(maxsize=None)
    def _get_client(self, vault_url: str) -> SecretClient:
        if vault_url not in self.clients:
            credential = DefaultAzureCredential()
            self.clients[vault_url] = SecretClient(vault_url=vault_url, credential=credential)
        return self.clients[vault_url]

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        """
        Fetch secrets from Azure Key Vault.

        The source URI should be in the format: <vault_url>/<secret_name>
        """
        fetched_values: dict[str, str] = {}
        for name, uri in sources.items():
            try:
                vault_url, secret_name = uri.rsplit("/", 1)
                client = self._get_client(vault_url)
                secret = client.get_secret(secret_name)
                if secret.value:
                    fetched_values[name] = secret.value
            except Exception:
                # Ignore errors for now
                pass
        return fetched_values
