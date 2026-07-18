import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_register_login_me_flow(client):
    r = await client.post(
        "/auth/register",
        json={
            "email": "Budi@Example.com",
            "password": "rahasia-123",
            "display_name": "Budi",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "budi@example.com"  # normalized to lowercase
    assert body["display_name"] == "Budi"
    assert "password" not in body and "password_hash" not in body

    r = await client.post(
        "/auth/login",
        json={"email": "budi@example.com", "password": "rahasia-123"},
    )
    assert r.status_code == 200
    token_body = r.json()
    assert token_body["token_type"] == "bearer"

    r = await client.get(
        "/me", headers={"Authorization": f"Bearer {token_body['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "budi@example.com"


async def test_wrong_password_rejected(client):
    await client.post(
        "/auth/register",
        json={"email": "siti@example.com", "password": "correct-horse-1"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "siti@example.com", "password": "wrong-password"},
    )
    assert r.status_code == 401
    # same message as unknown email — nothing leaked
    r2 = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-123"},
    )
    assert r2.status_code == 401
    assert r.json()["detail"] == r2.json()["detail"]


async def test_protected_route_requires_token(client):
    r = await client.get("/me")
    assert r.status_code == 401

    r = await client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


async def test_duplicate_email_conflict(client):
    payload = {"email": "dua@example.com", "password": "password-123"}
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 201
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 409


async def test_input_validation(client):
    r = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "password-123"}
    )
    assert r.status_code == 422

    r = await client.post(
        "/auth/register", json={"email": "ok@example.com", "password": "short"}
    )
    assert r.status_code == 422
