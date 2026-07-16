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
    avg_duration = await db.scalar(select(func.avg(AudioFile.duration_seconds)))

    return {
        "total_files": total,
        "done": done,
        "errors": errors,
        "success_rate": round(done / total * 100, 1) if total else 0,
        "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
        
        # TODO
        # total storage
        # files per user jedn
        # avg snr
        # most recent error
        # download urls : original, 128k, 64k + spectrograms

        # statuses
        # "pending": await db.scalar(select(func.count()).where(AudioFile.status == "pending")),
        # "processing": await db.scalar(select(func.count()).where(AudioFile.status == "processing")),
    }