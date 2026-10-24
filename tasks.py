"""Background tasks for scraping and email delivery.

Run a worker with:
    celery -A tasks.celery_app worker --loglevel=INFO
"""
import asyncio
import os

from celery import Celery

import books_scraper_full as scraper

BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")

celery_app = Celery(
    "fantasy_book_notifier",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(
    bind=True,
    name="tasks.scrape_publishers",
    max_retries=3,
    default_retry_delay=30,
)
def scrape_publishers_task(self, publishers, recipient_email):
    """Scrape selected publishers and send the result email.

    A worker crash can cause a task to be delivered again; scraper operations
    and email delivery should be made idempotent before adding side effects
    that must never be duplicated.
    """
    try:
        asyncio.run(scraper.run_for(publishers, recipient_email))
        return {
            "status": "completed",
            "publishers": publishers,
            "recipient": recipient_email,
        }
    except Exception as exc:
        raise self.retry(exc=exc, countdown=min(30 * (2 ** self.request.retries), 300))
