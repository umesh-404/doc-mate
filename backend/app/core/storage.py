"""S3-compatible object storage client (MinIO locally, R2/S3 in cloud).

The boto3 client is created lazily so importing this module never opens a
network connection. Raw uploaded files live here; only their storage keys are
persisted in the database.
"""

from __future__ import annotations

import uuid

import boto3
from botocore.client import Config

from app.core.config import settings

_client = None


def get_s3_client():
    """Return a lazily-created S3 client."""
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )
    return _client


def build_storage_key(patient_id: str, filename: str | None) -> str:
    """Build a collision-resistant object key for an uploaded file."""
    suffix = ""
    if filename and "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1].lower()
    return f"patients/{patient_id}/{uuid.uuid4().hex}{suffix}"


def put_object(key: str, body: bytes, content_type: str | None = None) -> None:
    """Upload bytes to the configured bucket under ``key``."""
    extra = {"ContentType": content_type} if content_type else {}
    get_s3_client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=body, **extra
    )


def get_object(key: str) -> bytes:
    """Download and return the raw bytes stored under ``key``."""
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()
