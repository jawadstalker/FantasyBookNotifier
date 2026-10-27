"""Real Redis/Celery broker smoke test; enabled in CI with a Redis service."""
import os
import uuid

import pytest

from celery import Celery
from celery.contrib.testing.worker import start_worker


@pytest.mark.integration
def test_celery_task_round_trip_through_redis():
    broker_url = os.getenv("CELERY_TEST_BROKER_URL")
    backend_url = os.getenv("CELERY_TEST_RESULT_BACKEND")
    if not broker_url or not backend_url:
        pytest.skip("set CELERY_TEST_BROKER_URL and CELERY_TEST_RESULT_BACKEND to enable Redis integration test")

    app = Celery(
        f"fantasybooknotifier-integration-{uuid.uuid4().hex}",
        broker=broker_url,
        backend=backend_url,
    )
    app.conf.update(
        task_always_eager=False,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        broker_connection_retry_on_startup=True,
        result_expires=300,
    )

    @app.task(name=f"tests.redis_round_trip_{uuid.uuid4().hex}")
    def echo_payload(payload):
        return {"received": payload, "worker": "ready"}

    try:
        with start_worker(
            app,
            pool="solo",
            concurrency=1,
            perform_ping_check=False,
            loglevel="WARNING",
        ):
            payload = {"job_id": str(uuid.uuid4()), "publishers": ["Publisher A"]}
            result = echo_payload.apply_async(args=[payload])
            assert result.get(timeout=20) == {"received": payload, "worker": "ready"}
            assert result.successful()
    finally:
        app.control.purge()
        app.close()
