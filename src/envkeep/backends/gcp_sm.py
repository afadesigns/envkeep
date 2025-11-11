from __future__ import annotations

from typing import TYPE_CHECKING

from ..plugins import Backend

if TYPE_CHECKING:
    from google.cloud import secretmanager


class GcpSecretManagerBackend(Backend):
    """Fetch secrets from Google Cloud Secret Manager."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self) -> secretmanager.SecretManagerServiceClient:
        if self._client is None:
            try:
                from google.cloud import secretmanager
            except ImportError as exc:
                raise ImportError(
                    "google-cloud-secret-manager is not installed. Run `pip install envkeep[gcp]`."
                ) from exc
            self._client = secretmanager.SecretManagerServiceClient()
        return self._client

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        client = self._get_client()
        results: dict[str, str] = {}
        for name, secret_id in sources.items():
            try:
                # The secret_id is expected to be in the format projects/*/secrets/*/versions/*
                response = client.access_secret_version(request={"name": secret_id})
                results[name] = response.payload.data.decode("UTF-8")
            except Exception:
                # Broadly catch exceptions from the gcloud client
                pass
        return results
