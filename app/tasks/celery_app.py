from celery import Celery
from app.setup.config import settings

celery_app = Celery(
    "audio_api",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.processing"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
