"""Health endpoints (no database writes)."""

from __future__ import annotations


async def test_health_ok(api_client):
    r = await api_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready_returns_status(api_client):
    r = await api_client.get("/ready")
    assert r.status_code in (200, 503)
    body = r.json()
    assert "status" in body
