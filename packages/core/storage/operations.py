import hashlib
import io
import os
from typing import BinaryIO

from minio import Minio


def bucket_exists(client: Minio, bucket: str) -> bool:
    """Return True if the bucket exists and is accessible."""
    return client.bucket_exists(bucket)


def ensure_bucket(client: Minio, bucket: str) -> None:
    """Raise RuntimeError if the bucket does not exist."""
    if not bucket_exists(client, bucket):
        raise RuntimeError(
            f"MinIO bucket '{bucket}' does not exist. "
            "Run the minio-bootstrap service or create it manually."
        )


def make_object_key(
    run_id: str, source_id: str, filename: str, artifact_type: str
) -> str:
    """Build a deterministic, collision-resistant object key.

    Format: {artifact_type}/{run_id}/{source_id}/{sha256_of_name}_{filename}
    The sha256 prefix keeps keys short and unique even if filenames repeat.
    """
    name_hash = hashlib.sha256(f"{run_id}/{source_id}/{filename}".encode()).hexdigest()[
        :16
    ]
    return f"{artifact_type}/{run_id}/{source_id}/{name_hash}_{filename}"


def object_uri(bucket: str, key: str) -> str:
    """Return a stable, opaque URI for an object."""
    return f"minio://{bucket}/{key}"


def upload_fileobj(
    client: Minio,
    bucket: str,
    key: str,
    data: BinaryIO,
    size: int,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload a file-like object to MinIO.

    Does not log file contents.
    Raises S3Error on failure.
    """
    client.put_object(
        bucket_name=bucket,
        object_name=key,
        data=data,
        length=size,
        content_type=content_type,
    )


def upload_bytes(
    client: Minio,
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload raw bytes to MinIO."""
    upload_fileobj(
        client,
        bucket,
        key,
        io.BytesIO(data),
        len(data),
        content_type,
    )


def default_bucket() -> str:
    """Return the configured default bucket name."""
    return os.environ["MINIO_DEFAULT_BUCKET"]
