"""Auth HTTP flows (Postgres required)."""

from __future__ import annotations


async def test_register_login_refresh_me(api_client, fresh_db):
    r = await api_client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "longpassword1",
            "full_name": "Owner User",
        },
    )
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == "owner@example.com".lower()
    assert "password" not in user

    r2 = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "longpassword1"},
    )
    assert r2.status_code == 200, r2.text
    tokens = r2.json()
    assert tokens["token_type"] == "bearer"
    assert "access_token" in tokens and "refresh_token" in tokens

    r3 = await api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert r3.status_code == 200
    assert r3.json()["id"] == user["id"]

    r4 = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert r4.status_code == 200
    body = r4.json()
    assert set(body.keys()) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"


async def test_register_duplicate_email(api_client, fresh_db):
    payload = {
        "email": "dup@example.com",
        "password": "longpassword1",
        "full_name": "A",
    }
    assert (await api_client.post("/api/v1/auth/register", json=payload)).status_code == 201
    r = await api_client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409
