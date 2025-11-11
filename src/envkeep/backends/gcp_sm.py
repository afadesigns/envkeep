import logging
from typing import TYPE_CHECKING

from ..plugins import Backend

if TYPE_CHECKING:
    from google.cloud.secretmanager_v1.services.secret_manager_service.client import (
        SecretManagerServiceClient,
    )

logger = logging.getLogger(__name__)


class GcpSecretManagerBackend(Backend):
    """Fetch secrets from Google Cloud Secret Manager."""

    def __init__(self) -> None:
        self._client: SecretManagerServiceClient | None = None

    def _get_client(self) -> SecretManagerServiceClient:
        if self._client is None:
            try:
                from google.cloud import secretmanager

                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError as exc:
                raise ImportError(
                    "google-cloud-secret-manager is not installed. Run `pip install envkeep[gcp]`.",
                ) from exc
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
                logger.exception("Failed to fetch secret: %s", secret_id)
        return results
