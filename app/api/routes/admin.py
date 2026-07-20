from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio import AudioFile
from app.setup.config import settings
from app.setup.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

def require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

@router.get("/stats", dependencies=[Depends(require_admin)])
async def stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AudioFile))
    done = await db.scalar(select(func.count()).where(AudioFile.status == "done"))
    errors = await db.scalar(select(func.count()).where(AudioFile.status == "error"))
    pending = await db.scalar(select(func.count()).where(AudioFile.status == "pending"))
    processing = await db.scalar(
        select(func.count()).where(AudioFile.status == "processing")
    )
    avg_duration = await db.scalar(select(func.avg(AudioFile.duration_seconds)))
    avg_bpm = await db.scalar(
        select(func.avg(AudioFile.bpm)).where(AudioFile.bpm > 0)
    )
    total_bytes = await db.scalar(select(func.sum(AudioFile.size_bytes)))

    files_per_user_rows = await db.execute(
        select(AudioFile.owner_id, func.count()).group_by(AudioFile.owner_id)
    )
    files_per_user = {row[0]: row[1] for row in files_per_user_rows}

    done_files = await db.execute(
        select(AudioFile.compression_results).where(
            AudioFile.status == "done",
            AudioFile.compression_results.isnot(None),
        )
    )
    snr_128k, snr_64k = [], []
    for (results,) in done_files:
        if "128k" in results and results["128k"].get("snr_db") is not None:
            snr_128k.append(results["128k"]["snr_db"])
        if "64k" in results and results["64k"].get("snr_db") is not None:
            snr_64k.append(results["64k"]["snr_db"])

    recent_error_rows = await db.execute(
        select(AudioFile.id, AudioFile.filename, AudioFile.error_message)
        .where(AudioFile.status == "error")
        .order_by(AudioFile.created_at.desc())
        .limit(5)
    )
    recent_errors = [
        {"id": r.id, "filename": r.filename, "error": r.error_message}
        for r in recent_error_rows
    ]

    return {
        "total_files": total,
        "done": done,
        "errors": errors,
        "pending": pending,
        "processing": processing,
        "success_rate": round(done / total * 100, 1) if total else 0,
        "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
        "avg_bpm": round(avg_bpm, 1) if avg_bpm else None,
        "total_storage_mb": round(total_bytes / 1024 / 1024, 2) if total_bytes else 0,
        "files_per_user": files_per_user,
        "avg_snr_db": {
            "128k": round(sum(snr_128k) / len(snr_128k), 2) if snr_128k else None,
            "64k": round(sum(snr_64k) / len(snr_64k), 2) if snr_64k else None,
        },
        "recent_errors": recent_errors,
    }