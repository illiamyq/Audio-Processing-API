from datetime import datetime
from pydantic import BaseModel


class AudioUploadOut(BaseModel):
    id: str
    filename: str
    status: str

    model_config = {"from_attributes": True}


class CompressionResult(BaseModel):
    size_bytes: int
    snr_db: float | None
    download_url: str | None = None


class AudioStatusOut(BaseModel):
    id: str
    filename: str
    status: str
    error_message: str | None
    duration_seconds: float | None
    sample_rate: int | None
    bpm: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioCompareOut(BaseModel):
    original_size_bytes: int
    results: dict[str, CompressionResult]
