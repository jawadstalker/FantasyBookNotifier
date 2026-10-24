"""Background tasks for publisher scraping and email notifications."""
import asyncio
import logging

import books_scraper_full as scraper
from celery_app import celery_app

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
    """Scrape selected publishers and send a notification email.

    Celery can retry after transient failures. A worker crash after sending an
    email but before acknowledging the task can lead to duplicate delivery;
    strict exactly-once delivery needs persistent idempotency records.
    """
    logger.info(
        "Scraping job %s started for %s (%s)",
        self.request.id,
        recipient_email,
        publishers,
    )
    asyncio.run(scraper.run_for(publishers, recipient_email))
    logger.info("Scraping job %s completed", self.request.id)
    return {"message": "scraping and notification completed", "publishers": publishers}
