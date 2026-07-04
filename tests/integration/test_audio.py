import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import AudioFile


@pytest.mark.asyncio
async def test_upload_audio(client: AsyncClient, auth_headers, user):
    fake_audio = b"RIFF" + b"\x00" * 100  # fake WAV-ish bytes
    resp = await client.post(
        "/audio",
        headers=auth_headers,
        files={"file": ("test.wav", fake_audio, "audio/wav")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["filename"] == "test.wav"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_wrong_type(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/audio",
        headers=auth_headers,
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/audio",
        files={"file": ("test.wav", b"data", "audio/wav")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_status_not_found(client: AsyncClient, auth_headers):
    resp = await client.get("/audio/nonexistent-id/status", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_audio(client: AsyncClient, auth_headers, db: AsyncSession, user):
    record = AudioFile(
        owner_id=user.id,
        filename="sample.mp3",
        original_key="originals/sample.mp3",
        content_type="audio/mpeg",
        size_bytes=1024,
        status="done",
    )
    db.add(record)
    await db.commit()

    resp = await client.get("/audio", headers=auth_headers)
    assert resp.status_code == 200
    assert any(r["filename"] == "sample.mp3" for r in resp.json())


@pytest.mark.asyncio
async def test_spectrogram_not_ready(client: AsyncClient, auth_headers, db: AsyncSession, user):
    record = AudioFile(
        owner_id=user.id,
        filename="pending.wav",
        original_key="originals/pending.wav",
        content_type="audio/wav",
        size_bytes=512,
        status="processing",
    )
    db.add(record)
    await db.commit()

    resp = await client.get(f"/audio/{record.id}/spectrogram", headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_audio(client: AsyncClient, auth_headers, db: AsyncSession, user):
    record = AudioFile(
        owner_id=user.id,
        filename="todelete.wav",
        original_key="originals/todelete.wav",
        content_type="audio/wav",
        size_bytes=256,
        status="done",
    )
    db.add(record)
    await db.commit()

    resp = await client.delete(f"/audio/{record.id}", headers=auth_headers)
    assert resp.status_code == 204
