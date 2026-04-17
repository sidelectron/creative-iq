"""Object storage: MinIO (S3-compatible) in development; GCS via google-cloud-storage elsewhere."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import aioboto3
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


async def upload_file(
    bucket: str,
    destination_path: str,
    data: bytes,
    content_type: str,
) -> str:
    """Upload bytes to bucket/key; returns ``bucket/destination_path``."""
    if _use_minio():
        kwargs = _s3_client_kwargs()
        session = aioboto3.Session()
        async with session.client("s3", **kwargs) as client:
            await client.put_object(
                Bucket=bucket,
                Key=destination_path,
                Body=data,
                ContentType=content_type,
            )
        return f"{bucket}/{destination_path}"

    def _gcs_upload() -> None:
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=settings.gcs_project_id)
        blob = client.bucket(bucket).blob(destination_path)
        blob.upload_from_string(data, content_type=content_type)

    await asyncio.to_thread(_gcs_upload)
    return f"{bucket}/{destination_path}"


async def download_file(bucket: str, path: str) -> bytes:
    """Download object bytes."""
    if _use_minio():
        kwargs = _s3_client_kwargs()
        session = aioboto3.Session()
        async with session.client("s3", **kwargs) as client:
            resp = await client.get_object(Bucket=bucket, Key=path)
            body = resp["Body"]
            return await body.read()

    def _gcs_download() -> bytes:
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=settings.gcs_project_id)
        blob = client.bucket(bucket).blob(path)
        return blob.download_as_bytes()

    return await asyncio.to_thread(_gcs_download)


async def generate_presigned_url(
    bucket: str,
    path: str,
    expiry_minutes: int,
) -> str:
    """Generate a presigned GET URL."""
    if _use_minio():
        kwargs = _s3_client_kwargs()

        def _sync_sign() -> str:
            client = boto3.client("s3", **kwargs)
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": path},
                ExpiresIn=expiry_minutes * 60,
            )

        return await asyncio.to_thread(_sync_sign)

    def _gcs_sign() -> str:
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=settings.gcs_project_id)
        blob = client.bucket(bucket).blob(path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiry_minutes),
            method="GET",
        )

    return await asyncio.to_thread(_gcs_sign)


async def delete_file(bucket: str, path: str) -> None:
    """Delete an object."""
    if _use_minio():
        kwargs = _s3_client_kwargs()
        session = aioboto3.Session()
        async with session.client("s3", **kwargs) as client:
            await client.delete_object(Bucket=bucket, Key=path)
        return

    def _gcs_delete() -> None:
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=settings.gcs_project_id)
        client.bucket(bucket).blob(path).delete()

    await asyncio.to_thread(_gcs_delete)


async def list_files_by_prefix(bucket: str, prefix: str) -> list[str]:
    """Return object keys under prefix."""
    if _use_minio():
        kwargs = _s3_client_kwargs()
        session = aioboto3.Session()
        keys: list[str] = []
        async with session.client("s3", **kwargs) as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []) or []:
                    keys.append(obj["Key"])
        return keys

    def _gcs_list() -> list[str]:
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=settings.gcs_project_id)
        blobs = client.list_blobs(bucket, prefix=prefix)
        return [b.name for b in blobs]

    return await asyncio.to_thread(_gcs_list)
