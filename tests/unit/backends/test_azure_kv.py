from __future__ import annotations

from unittest.mock import MagicMock, patch

from envkeep.backends.azure_kv import AzureKeyVaultBackend


def test_azure_kv_backend_fetch():
    """Verify that the Azure Key Vault backend fetches secrets correctly."""
    with patch("envkeep.backends.azure_kv.SecretClient") as mock_secret_client:
        mock_secret = MagicMock()
        mock_secret.value = "secret_value"
        mock_secret_client.return_value.get_secret.return_value = mock_secret

        backend = AzureKeyVaultBackend()
        sources = {
            "MY_SECRET": "https://my-vault.vault.azure.net/secrets/my-secret"
        }
        result = backend.fetch(sources)

        assert result == {"MY_SECRET": "secret_value"}
        mock_secret_client.return_value.get_secret.assert_called_once_with(
            "my-secret"
        )
