from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..plugins import Backend

if TYPE_CHECKING:
    import boto3


class AwsSecretsManagerBackend(Backend):
    """Fetch secrets from AWS Secrets Manager."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self) -> boto3.client:
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ImportError("boto3 is not installed. Run `pip install envkeep[aws]`.") from exc
            self._client = boto3.client("secretsmanager")
        return self._client

    def fetch(self, sources: dict[str, str]) -> dict[str, str]:
        client = self._get_client()
        results: dict[str, str] = {}
        for name, secret_id in sources.items():
            try:
                response = client.get_secret_value(SecretId=secret_id)
                results[name] = response["SecretString"]
            except client.exceptions.ResourceNotFoundException:
                # You might want to log this
                pass
            except Exception:
                # Broadly catch other exceptions from boto3
                pass
        return results
