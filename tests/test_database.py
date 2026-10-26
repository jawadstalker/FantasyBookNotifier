import pytest

import database


@pytest.fixture()
def db(tmp_path):
    database.configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    database.init_db()
    yield database
    database.engine.dispose()


def test_subscription_is_upserted_and_email_normalized(db):
    db.upsert_subscription(" Reader@Example.com ", ["Publisher A"])
    db.upsert_subscription("reader@example.COM", ["Publisher B"])

    with db.SessionLocal() as session:
        subscription = session.query(db.Subscription).one()
        assert subscription.email == "reader@example.com"
        assert subscription.publishers == ["Publisher B"]
        assert subscription.active is True


def test_job_lifecycle_is_persisted(db):
    db.create_job("12345678-1234-1234-1234-123456789abc", "reader@example.com", ["Publisher A"])
    assert db.get_job("12345678-1234-1234-1234-123456789abc")["state"] == "queued"

    db.update_job(
        "12345678-1234-1234-1234-123456789abc",
        "running",
        started=True,
    )
    db.update_job(
        "12345678-1234-1234-1234-123456789abc",
        "completed",
        result={"message": "done"},
        finished=True,
    )
    job = db.get_job("12345678-1234-1234-1234-123456789abc")
    assert job["state"] == "completed"
    assert job["result"] == {"message": "done"}
    assert job["started_at"] is not None
    assert job["finished_at"] is not None


def test_missing_job_returns_none(db):
    assert db.get_job("12345678-1234-1234-1234-123456789abc") is None


def test_email_delivery_is_skipped_after_success(db):
    key = "scraping-job:12345678-1234-1234-1234-123456789abc"
    assert db.begin_email_delivery(key, "reader@example.com") is True
    db.finish_email_delivery(key, sent=True)

    assert db.begin_email_delivery(key, "reader@example.com") is False

    with db.SessionLocal() as session:
        delivery = session.query(db.EmailDelivery).one()
        assert delivery.status == "sent"
        assert delivery.sent_at is not None


def test_failed_email_delivery_can_be_retried(db):
    key = "scraping-job:12345678-1234-1234-1234-123456789abc"
    assert db.begin_email_delivery(key, "reader@example.com") is True
    db.finish_email_delivery(key, sent=False, error="SMTP unavailable")

    assert db.begin_email_delivery(key, "reader@example.com") is True
    with db.SessionLocal() as session:
        delivery = session.query(db.EmailDelivery).one()
        assert delivery.status == "sending"
        assert delivery.error is None
