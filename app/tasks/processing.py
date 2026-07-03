import io
import os
import tempfile

import ffmpeg
import librosa
import matplotlib
import numpy as np
import soundfile as sf

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.setup.config import settings
from app.models.audio import AudioFile
from app.services import storage
from app.tasks.celery_app import celery_app


def _sync_engine():
    return create_engine(settings.DATABASE_URL_SYNC)


def _get_audio_record(session: Session, audio_id: str) -> AudioFile:
    record = session.get(AudioFile, audio_id)
    if record is None:
        raise ValueError(f"AudioFile {audio_id} not found")
    return record


def _compute_snr(original: np.ndarray, compressed: np.ndarray) -> float:
    min_len = min(len(original), len(compressed))
    orig = original[:min_len].astype(np.float64)
    comp = compressed[:min_len].astype(np.float64)
    signal_power = np.mean(orig**2)
    noise_power = np.mean((orig - comp) ** 2)
    if noise_power == 0:
        return float("inf")
    return float(10 * np.log10(signal_power / noise_power))


def _generate_spectrogram(y: np.ndarray, sr: int) -> bytes:
    fig, ax = plt.subplots(figsize=(10, 4))
    S_db = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
    img = librosa.display.specshow(S_db, sr=sr, x_axis="time", y_axis="hz", ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set_title("Spectrogram")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _transcode_to_mp3(input_path: str, output_path: str, bitrate: str):
    ffmpeg.input(input_path).output(output_path, audio_bitrate=bitrate, acodec="libmp3lame").overwrite_output().run(
        quiet=True
    )


@celery_app.task(bind=True, max_retries=2)
def process_audio(self, audio_id: str):
    engine = _sync_engine()

    with Session(engine) as session:
        record = _get_audio_record(session, audio_id)
        record.status = "processing"
        original_key = record.original_key
        filename = record.filename
        session.commit()

    try:
        raw = storage.download_bytes(original_key)

        with tempfile.TemporaryDirectory() as tmpdir:
            original_path = os.path.join(tmpdir, "original" + _ext(filename))
            with open(original_path, "wb") as f:
                f.write(raw)

            y, sr = librosa.load(original_path, sr=None, mono=True)
            duration = librosa.get_duration(y=y, sr=sr)
            bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(np.asarray(bpm).flat[0])

            spectrogram_png = _generate_spectrogram(y, sr)
            spec_key = f"spectrograms/{audio_id}.png"
            storage.upload_bytes(spec_key, spectrogram_png, content_type="image/png")

            compression_results = {}
            for bitrate in ("128k", "64k"):
                out_path = os.path.join(tmpdir, f"compressed_{bitrate}.mp3")
                _transcode_to_mp3(original_path, out_path, bitrate)

                with open(out_path, "rb") as f:
                    compressed_bytes = f.read()

                s3_key = f"compressed/{audio_id}_{bitrate}.mp3"
                storage.upload_bytes(s3_key, compressed_bytes, content_type="audio/mpeg")

                y_comp, _ = librosa.load(out_path, sr=sr, mono=True)
                snr = _compute_snr(y, y_comp)

                compression_results[bitrate] = {
                    "key": s3_key,
                    "size_bytes": len(compressed_bytes),
                    "snr_db": round(snr, 2),
                }

        with Session(engine) as session:
            record = _get_audio_record(session, audio_id)
            record.status = "done"
            record.duration_seconds = round(duration, 2)
            record.sample_rate = int(sr)
            record.bpm = round(float(bpm), 1)
            record.spectrogram_key = spec_key
            record.compression_results = compression_results
            session.commit()

    except Exception as exc:
        with Session(engine) as session:
            record = _get_audio_record(session, audio_id)
            record.status = "error"
            record.error_message = str(exc)
            session.commit()
        raise self.retry(exc=exc, countdown=10)


def _ext(filename: str) -> str:
    _, ext = os.path.splitext(filename)
    return ext or ".audio"