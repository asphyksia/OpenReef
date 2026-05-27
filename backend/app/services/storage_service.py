"""MinIO / R2 / S3-compatible storage service.

Uses boto3 with endpoint_url support — same code works for MinIO (dev),
R2 (prod), or any S3-compatible backend.
"""

import logging
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_bucket = settings.r2_bucket_name


def _get_client():
    """Lazy singleton boto3 S3 client."""
    global _client
    if _client is None:
        session = boto3.Session(
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        _client = session.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url or None,
            config=Config(signature_version="s3v4"),
        )
    return _client


def ensure_bucket():
    """Create bucket if it doesn't exist. Call once at startup."""
    client = _get_client()
    try:
        client.head_bucket(Bucket=_bucket)
        logger.info("Storage bucket '%s' exists", _bucket)
    except ClientError as e:
        status = e.response.get("Error", {}).get("Code")
        if status in ("404", "NoSuchBucket"):
            logger.info("Creating storage bucket '%s'", _bucket)
            client.create_bucket(Bucket=_bucket)
        else:
            raise


def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to storage. Returns the key."""
    client = _get_client()
    client.put_object(
        Bucket=_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    logger.info("Uploaded %d bytes to %s", len(data), key)
    return key


def upload_stream(file_like, key: str, content_type: str = "application/octet-stream") -> str:
    client = _get_client()
    client.put_object(
        Bucket=_bucket,
        Key=key,
        Body=file_like,
        ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    return keytype: str = "application/octet-stream") -> str:
    """Upload from a file-like object (streaming, no full read into memory)."""
    client = _get_client()
    client.put_object(
        Bucket=_bucket,
        Key=key,
        Body=file_like,
        ContentType=content_type,
    )
    logger.info("Uploaded stream to %s", key)
    return key


def download_bytes(key: str) -> bytes:
    """Download file bytes from storage."""
    client = _get_client()
    response = client.get_object(Bucket=_bucket, Key=key)
    return response["Body"].read()


def delete_file(key: str) -> None:
    """Delete a file from storage."""
    client = _get_client()
    try:
        client.delete_object(Bucket=_bucket, Key=key)
        logger.info("Deleted %s", key)
    except ClientError as e:
        logger.warning("Failed to delete %s: %s", key, e)


def presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned download URL."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def head_object(key: str) -> dict | None:
    """Check if an object exists and return its metadata, or None if not found."""
    client = _get_client()
    try:
        response = client.head_object(Bucket=_bucket, Key=key)
        return {
            "content_length": response.get("ContentLength", 0),
            "content_type": response.get("ContentType", ""),
            "last_modified": response.get("LastModified"),
        }
    except ClientError as e:
        status = e.response.get("Error", {}).get("Code")
        if status in ("404", "NoSuchKey"):
            return None
        raise
