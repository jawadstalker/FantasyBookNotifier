"""Task orchestration tests using a temporary database and a fake async scraper."""
import importlib
import sys
import types
from types import SimpleNamespace
from uuid import uuid4

import pytest

import database


@pytest.fixture()
def task_module(tmp_path, monkeypatch):
    database.configure_database(f"sqlite:///{tmp_path / 'tasks.db'}")
    database.init_db()

    scraper_stub = types.ModuleType("books_scraper_full")

    async def unused_run_for(_publishers, _recipient):
        raise AssertionError("test must replace run_for")

    scraper_stub.run_for = unused_run_for
    monkeypatch.setitem(sys.modules, "books_scraper_full", scraper_stub)
    sys.modules.pop("tasks", None)
    module = importlib.import_module("tasks")
    yield module
    sys.modules.pop("tasks", None)
    database.engine.dispose()


def _fake_task_self(job_id, retries=0):
    return SimpleNamespace(
        request=SimpleNamespace(id=job_id, retries=retries),
        max_retries=3,
    )


def test_successful_task_persists_job_and_delivery(task_module, monkeypatch):
    job_id = str(uuid4())
    database.create_job(job_id, "reader@example.com", ["Publisher A"])
    calls = []

    async def fake_run_for(publishers, recipient):
        calls.append((publishers, recipient))

    monkeypatch.setattr(task_module, "run_for", fake_run_for)
    result = task_module.scrape_publishers_task.run(
        _fake_task_self(job_id), ["Publisher A"], "reader@example.com"
    )

    assert result["message"] == "scraping and notification completed"
    assert calls == [(["Publisher A"], "reader@example.com")]
    assert database.get_job(job_id)["state"] == "completed"
    with database.SessionLocal() as session:
        delivery = session.query(database.EmailDelivery).one()
        assert delivery.status == "sent"
        assert delivery.sent_at is not None


def test_failed_task_records_retryable_state(task_module, monkeypatch):
    job_id = str(uuid4())
    database.create_job(job_id, "reader@example.com", ["Publisher A"])

    async def fail_run_for(_publishers, _recipient):
        raise RuntimeError("SMTP test failure")

    monkeypatch.setattr(task_module, "run_for", fail_run_for)
    with pytest.raises(RuntimeError, match="SMTP test failure"):
        task_module.scrape_publishers_task.run(
            _fake_task_self(job_id), ["Publisher A"], "reader@example.com"
        )

    job = database.get_job(job_id)
    assert job["state"] == "retrying"
    assert job["error"] == "SMTP test failure"
    with database.SessionLocal() as session:
        delivery = session.query(database.EmailDelivery).one()
        assert delivery.status == "failed"
        assert delivery.error == "SMTP test failure"
