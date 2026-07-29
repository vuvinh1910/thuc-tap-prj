"""
Celery application factory.
Configure broker, result backend, and task serialization.
"""

from celery import Celery

from src.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "ragbot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.workers.tasks.ingest_task"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,

    # Routing — all ingest tasks go to the 'ingest' queue
    task_routes={"src.workers.tasks.ingest_task.*": {"queue": "ingest"}},

    # Retry / reliability
    task_acks_late=True,           # Only ack after task completes (safer)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # Prevent memory issues with large PDFs

    # Result expiry (24 hours)
    result_expires=86400,
)
