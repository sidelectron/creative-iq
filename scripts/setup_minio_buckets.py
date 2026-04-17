"""Create Phase 1 MinIO buckets (idempotent). Requires MinIO to be reachable."""

from __future__ import annotations

import logging
import os
import sys
import time
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("setup_minio_buckets")


def _wait_for_minio(health_url: str, attempts: int = 60, delay_sec: float = 2.0) -> None:
    for i in range(attempts):
        try:
            with urllib.request.urlopen(health_url, timeout=3) as resp:
                if resp.status == 200:
                    log.info("MinIO is healthy (%s)", health_url)
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        log.info("Waiting for MinIO (%s/%s)...", i + 1, attempts)
        time.sleep(delay_sec)
    log.error("MinIO did not become healthy in time: %s", health_url)
    sys.exit(1)


def main() -> None:
    endpoint = os.environ.get("MINIO_ENDPOINT_URL", "http://localhost:9000").rstrip("/")
    access = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    region = os.environ.get("MINIO_REGION", "us-east-1")

    required = (
        "STORAGE_BUCKET_RAW_ADS",
        "STORAGE_BUCKET_EXTRACTED",
        "STORAGE_BUCKET_MODELS",
        "STORAGE_BUCKET_BRAND_ASSETS",
    )
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        log.error("Missing environment variables: %s", ", ".join(missing))
        sys.exit(1)
    buckets = [os.environ[k] for k in required]

    health_url = f"{endpoint}/minio/health/live"
    _wait_for_minio(health_url)

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
    )
    for name in buckets:
        try:
            client.head_bucket(Bucket=name)
            log.info("Bucket exists: %s", name)
        except ClientError:
            client.create_bucket(Bucket=name)
            log.info("Created bucket: %s", name)
    log.info("All buckets ready: %s", ", ".join(buckets))


if __name__ == "__main__":
    main()
