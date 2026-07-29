"""S3-compatible file storage abstraction (MinIO today, swappable for NAS/other object storage)."""
import io

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()


class FileStorage:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
            use_ssl=settings.S3_USE_SSL,
        )
        self._bucket = settings.S3_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get_object(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def get_object_stream(self, key: str) -> io.BytesIO:
        return io.BytesIO(self.get_object(key))

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def presigned_get_url(self, key: str, expires_in: int = 300) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expires_in
        )


_storage_instance: FileStorage | None = None


def get_storage() -> FileStorage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = FileStorage()
    return _storage_instance
