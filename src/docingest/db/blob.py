from io import BytesIO

from minio import Minio

from docingest.config import settings

_client: Minio | None = None


def get_blob_client() -> Minio:
    """Get or create the MinIO client (singleton)."""
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def close_blob() -> None:
    """Release the MinIO client reference."""
    global _client
    _client = None


def ensure_bucket(client: Minio) -> None:
    """Ensure the configured bucket exists, creating it if needed."""
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def upload_blob(
    client: Minio,
    tenant_id: str,
    blob_path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload data to MinIO. Returns the full object path."""
    object_name = f"{tenant_id}/{blob_path}"
    client.put_object(
        settings.minio_bucket,
        object_name,
        BytesIO(data),
        len(data),
        content_type=content_type,
    )
    return object_name


def download_blob(
    client: Minio,
    tenant_id: str,
    blob_path: str,
) -> bytes:
    """Download data from MinIO."""
    object_name = f"{tenant_id}/{blob_path}"
    response = client.get_object(settings.minio_bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_blob(
    client: Minio,
    tenant_id: str,
    blob_path: str,
) -> None:
    """Delete an object from MinIO."""
    object_name = f"{tenant_id}/{blob_path}"
    client.remove_object(settings.minio_bucket, object_name)
