"""
End-to-end decomposition against Docker Compose.

Requires: compose up, tests/fixtures/sample.mp4, RUN_DOCKER_INTEGRATION=1.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample.mp4"


@pytest.mark.skipif(
    os.environ.get("RUN_DOCKER_INTEGRATION") != "1",
    reason="Set RUN_DOCKER_INTEGRATION=1 and start docker compose to run",
)
@pytest.mark.skipif(not FIXTURE.is_file(), reason=f"Missing fixture video: {FIXTURE}")
@pytest.mark.asyncio
async def test_upload_then_decomposed_status() -> None:
    base = os.environ.get("INTEGRATION_API_URL", "http://127.0.0.1:8000")
    async with httpx.AsyncClient(base_url=base, timeout=120.0) as client:
        r = await client.post(
            f"{os.environ.get('API_V1_PREFIX', '/api/v1')}/auth/login",
            json={"email": "skip@example.com", "password": "x"},
        )
        if r.status_code != 200:
            pytest.skip("Integration auth not configured for this environment")

        token = r.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        brand_id = os.environ.get("INTEGRATION_BRAND_ID", "")
        if not brand_id:
            pytest.skip("INTEGRATION_BRAND_ID not set")

        with FIXTURE.open("rb") as f:
            up = await client.post(
                f"{os.environ.get('API_V1_PREFIX', '/api/v1')}/brands/{brand_id}/ads/upload",
                headers=headers,
                files={"video": ("sample.mp4", f, "video/mp4")},
                data={"platform": "meta"},
            )
        assert up.status_code in (200, 201), up.text
        ad_id = up.json()["id"]

        deadline = time.time() + 300
        status_val = ""
        while time.time() < deadline:
            st = await client.get(
                f"{os.environ.get('API_V1_PREFIX', '/api/v1')}/ads/{ad_id}/status",
                headers=headers,
            )
            assert st.status_code == 200
            status_val = st.json()["status"]
            if status_val == "decomposed":
                break
            if status_val == "failed":
                pytest.fail(st.json())
            await __import__("asyncio").sleep(2)

        assert status_val == "decomposed"
        fp = await client.get(
            f"{os.environ.get('API_V1_PREFIX', '/api/v1')}/ads/{ad_id}/fingerprint",
            headers=headers,
        )
        assert fp.status_code == 200
        attrs = fp.json()["attributes"]
        assert "duration_seconds" in attrs
