from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.setup.database import get_db
from app.setup.security import get_current_user
from app.setup.config import settings
from app.models.user import User
from app.schemas.audio import (
    AudioUploadOut,
    AudioStatusOut,
    AudioCompareOut,
    CompressionResult,
)
from app.services import storage
from app.services.audio import get_audio, list_audio, create_audio_record
from app.tasks.processing import process_audio

router = APIRouter(prefix="/audio", tags=["audio"])




# cleanup ? TODO consider (move to service layer?)
# async def _get_owned_audio(audio_id: str, db: AsyncSession, user: User):
#     """Fetch audio record and verify ownership."""
#     return await get_audio(db, audio_id, user.id)


@router.post("", response_model=AudioUploadOut, status_code=status.HTTP_201_CREATED)
async def upload_audio(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in settings.ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {file.content_type}",
        )

    raw = await file.read()
    if len(raw) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")

    record = await create_audio_record(
        db,
        owner_id=current_user.id,
        filename=file.filename,
        original_key="",  # filled down
        content_type=file.content_type,
        size_bytes=len(raw),
    )

    s3_key = f"originals/{current_user.id}/{record.id}/{file.filename}"
    storage.upload_bytes(s3_key, raw, content_type=file.content_type)

    from app.services.audio import update_audio

    await update_audio(db, record, original_key=s3_key)

    # asynchronos
    process_audio.delay(record.id)

    return record

# TODO move get + ownership check into a dependency/helper.

@router.get("", response_model=list[AudioStatusOut])
async def list_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_audio(db, current_user.id)


@router.get("/{audio_id}/status", response_model=AudioStatusOut)
async def get_status(
    audio_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_audio(db, audio_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    return record


@router.get("/{audio_id}/spectrogram")
async def get_spectrogram(
    audio_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_audio(db, audio_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    if record.status != "done" or not record.spectrogram_key:
        raise HTTPException(status_code=409, detail="Spectrogram not ready")

    png = storage.download_bytes(record.spectrogram_key)
    return Response(content=png, media_type="image/png")


@router.get("/{audio_id}/compare", response_model=AudioCompareOut)
async def compare_compression(
    audio_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_audio(db, audio_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    if record.status != "done" or not record.compression_results:
        raise HTTPException(status_code=409, detail="Processing not complete")

    results = {
        bitrate: CompressionResult(
            size_bytes=data["size_bytes"],
            snr_db=data["snr_db"],
            download_url=storage.presigned_url(data["key"]),
        )
        for bitrate, data in record.compression_results.items()
    }

    return AudioCompareOut(
        original_size_bytes=record.size_bytes,
        results=results,
    )

# TODO  toadd structured logging for uploads and processing failures (010,201,..).

@router.delete("/{audio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_audio(
    audio_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_audio(db, audio_id, current_user.id)
    if not record:
        raise HTTPException(status_code=404, detail="Not found")

    # todo to update cleanup
    keys_to_delete = [record.original_key]

    if record.spectrogram_key:
        keys_to_delete.append(record.spectrogram_key)

    if record.compression_results:
        keys_to_delete += [v["key"] for v in record.compression_results.values()]

    for key in keys_to_delete:
        try:
            storage.delete_object(key)
        except Exception:
            pass

    await db.delete(record)
    await db.commit()