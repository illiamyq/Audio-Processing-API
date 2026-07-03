import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    resp = await client.post("/auth/register", json={"email": "new@example.com", "password": "pass123"})
    assert resp.status_code == 201
    assert resp.json()["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient, user):
    resp = await client.post("/auth/register", json={"email": user.email, "password": "pass"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient, user):
    resp = await client.post("/auth/login", data={"username": user.email, "password": "password123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, user):
    resp = await client.post("/auth/login", data={"username": user.email, "password": "wrong"})
    assert resp.status_code == 401
