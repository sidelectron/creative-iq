"""Synchronous object storage for Celery worker (MinIO / GCS)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import boto3
from botocore.client import Config as BotoConfig

from shared.config.settings import settings


def _use_minio() -> bool:
    return settings.environment.lower() == "development"


def _s3_client_kwargs() -> dict[str, Any]:
    if not _use_minio():
        return {}
    return {
        "endpoint_url": settings.minio_endpoint_url,
        "aws_access_key_id": settings.minio_access_key,
        "aws_secret_access_key": settings.minio_secret_key,
        "region_name": settings.minio_region,
        "use_ssl": settings.minio_use_ssl,
        "config": BotoConfig(signature_version="s3v4"),
    }


def download_bytes(bucket: str, key: str) -> bytes:
    if _use_minio():
        client = boto3.client("s3", **_s3_client_kwargs())
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client(project=settings.gcs_project_id)
    return client.bucket(bucket).blob(key).download_as_bytes()


def upload_bytes(bucket: str, key: str, data: bytes, content_type: str) -> str:
    if _use_minio():
        client = boto3.client("s3", **_s3_client_kwargs())
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return f"{bucket}/{key}"

    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client(project=settings.gcs_project_id)
    blob = client.bucket(bucket).blob(key)
    blob.upload_from_string(data, content_type=content_type)
    return f"{bucket}/{key}"


def list_keys_by_prefix(bucket: str, prefix: str) -> list[str]:
    if _use_minio():
        client = boto3.client("s3", **_s3_client_kwargs())
        keys: list[str] = []
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []) or []:
                keys.append(obj["Key"])
        return keys

    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client(project=settings.gcs_project_id)
    return [b.name for b in client.list_blobs(bucket, prefix=prefix)]


def delete_object(bucket: str, key: str) -> None:
    if _use_minio():
        client = boto3.client("s3", **_s3_client_kwargs())
        client.delete_object(Bucket=bucket, Key=key)
        return

    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client(project=settings.gcs_project_id)
    client.bucket(bucket).blob(key).delete()


def parse_bucket_key(gcs_path: str) -> tuple[str, str]:
    """Split ``bucket/key`` into bucket and object key."""
    bucket, _, key = gcs_path.partition("/")
    return bucket, key


def presigned_get_url(bucket: str, key: str, expiry_minutes: int) -> str:
    if _use_minio():
        client = boto3.client("s3", **_s3_client_kwargs())
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry_minutes * 60,
        )

    from google.cloud import storage as gcs_storage

    client = gcs_storage.Client(project=settings.gcs_project_id)
    blob = client.bucket(bucket).blob(key)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=expiry_minutes),
        method="GET",
    )
