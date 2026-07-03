# Audio Processing API

REST API for audio file upload, background transcoding, and compression analysis.

**Stack:** FastAPI · Celery · Redis · PostgreSQL · MinIO (S3) · Docker · GitHub Actions

MinIO console: (minioadmin / minioadmin).

## API reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns JWT |
| POST | `/audio` | Upload audio file |
| GET | `/audio` | List your files |
| GET | `/audio/{id}/status` | Job status + metadata |
| GET | `/audio/{id}/spectrogram` | PNG spectrogram image |
| GET | `/audio/{id}/compare` | SNR + size comparison per bitrate |
| DELETE | `/audio/{id}` | Delete file and all derived assets |

---
```json
## Example response of GET  `/audio/{id}/compare`

{
  "original_size_bytes": 889988,
  "results": {
    "128k": {
      "size_bytes": 168870,
      "snr_db": 23.27,
      "download_url": "http://minio:9000/audio-files/compressed/[generated url]"
    },
    "64k": {
      "size_bytes": 88413,
      "snr_db": 7.57,
      "download_url": "http://minio:9000/audio-files/compressed/[generated url]"
    }
  }
}
```