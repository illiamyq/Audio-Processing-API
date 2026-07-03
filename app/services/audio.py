from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import AudioFile


async def get_audio(db: AsyncSession, audio_id: str, owner_id: str) -> AudioFile | None:
    result = await db.execute(
        select(AudioFile).where(AudioFile.id == audio_id, AudioFile.owner_id == owner_id)
    )
    return result.scalar_one_or_none()


async def list_audio(db: AsyncSession, owner_id: str, page: int = 1, limit: int = 20) -> list[AudioFile]:
    offset = (page - 1) * limit
    result = await db.execute(
        select(AudioFile)
        .where(AudioFile.owner_id == owner_id)
        .order_by(AudioFile.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all())


async def create_audio_record(
    db: AsyncSession,
    owner_id: str,
    filename: str,
    original_key: str,
    content_type: str,
    size_bytes: int,
) -> AudioFile:
    audio = AudioFile(
        owner_id=owner_id,
        filename=filename,
        original_key=original_key,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    db.add(audio)
    await db.commit()
    await db.refresh(audio)
    return audio


async def update_audio(db: AsyncSession, audio: AudioFile, **kwargs) -> AudioFile:
    for key, value in kwargs.items():
        setattr(audio, key, value)
    await db.commit()
    await db.refresh(audio)
    return audio