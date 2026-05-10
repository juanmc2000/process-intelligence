import os

from minio import Minio


def make_storage_client() -> Minio:
    """Build a MinIO client from environment variables.

    Required env vars:
        MINIO_ENDPOINT       host:port of the MinIO server (e.g. minio:9000)
        MINIO_ROOT_USER      access key
        MINIO_ROOT_PASSWORD  secret key
    Optional:
        MINIO_SECURE         set to "true" to use HTTPS (default: false)
    """
    endpoint = os.environ["MINIO_ENDPOINT"]
    access_key = os.environ["MINIO_ROOT_USER"]
    secret_key = os.environ["MINIO_ROOT_PASSWORD"]
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
