"""Brand CRUD and RBAC (Postgres required)."""

from __future__ import annotations


async def _register_and_login(client, email: str, password: str = "longpassword1"):
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0]},
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


async def test_create_list_brand(api_client, fresh_db):
    token = await _register_and_login(api_client, "brandowner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = await api_client.post(
        "/api/v1/brands",
        json={"name": "Acme", "industry": "software"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    brand = r.json()
    assert brand["name"] == "Acme"
    assert brand["member_count"] >= 1

    r2 = await api_client.get("/api/v1/brands", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
