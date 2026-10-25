"""Background tasks for publisher scraping and email notifications."""
import asyncio
import logging

from books_scraper_full import run_for
from celery_app import celery_app
from database import (
    begin_email_delivery,
    finish_email_delivery,
    update_job,
)

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.scrape_publishers_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def scrape_publishers_task(self, publishers, recipient_email):
    """Scrape publishers and send a notification with persistent job tracking.

    The delivery key prevents re-sending after the database has recorded a
    successful send. SMTP cannot provide true exactly-once delivery: if a
    worker crashes after the server accepts a message but before the database
    records success, a retry may still send a duplicate.
    """
    job_id = self.request.id
    delivery_key = f"scraping-job:{job_id}"
    update_job(job_id, "running", started=True)

    try:
        should_send = begin_email_delivery(delivery_key, recipient_email)
        if not should_send:
            result = {
                "message": "email was already marked as sent; duplicate delivery skipped",
                "publishers": publishers,
            }
            update_job(job_id, "completed", result=result, finished=True)
            return result

        asyncio.run(run_for(publishers, recipient_email))
        finish_email_delivery(delivery_key, sent=True)
        result = {
            "message": "scraping and notification completed",
            "publishers": publishers,
        }
        update_job(job_id, "completed", result=result, finished=True)
        logger.info("Scraping job %s completed", job_id)
        return result
    except Exception as exc:
        logger.exception("Scraping job %s failed on attempt %s", job_id, self.request.retries + 1)
        try:
            finish_email_delivery(delivery_key, sent=False, error=str(exc))
            will_retry = self.request.retries < self.max_retries
            update_job(
                job_id,
                "retrying" if will_retry else "failed",
                error=str(exc),
                finished=not will_retry,
            )
        except Exception:
            logger.exception("Could not persist failure state for job %s", job_id)
        raise
