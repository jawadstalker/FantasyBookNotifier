"""Persistent storage for subscriptions, scraping jobs, and email deliveries."""
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, JSON, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///fantasybooknotifier.db")
_ENGINE_OPTIONS = {"pool_pre_ping": True}
_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_CONNECT_ARGS, **_ENGINE_OPTIONS)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    publishers: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ScrapingJob(Base):
    __tablename__ = "scraping_jobs"

    # Celery task UUID is also the stable public job identifier.
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    publishers: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique per scraping job; used to avoid re-sending after a completed delivery.
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(254), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    Base.metadata.create_all(bind=engine)


def upsert_subscription(email, publishers):
    normalized_email = email.strip().lower()
    with session_scope() as session:
        subscription = session.scalar(select(Subscription).where(Subscription.email == normalized_email))
        if subscription is None:
            subscription = Subscription(email=normalized_email, publishers=list(publishers), active=True)
            session.add(subscription)
        else:
            subscription.publishers = list(publishers)
            subscription.active = True
            subscription.updated_at = utcnow()
    return normalized_email


def create_job(job_id, email, publishers):
    with session_scope() as session:
        session.add(ScrapingJob(
            id=job_id,
            email=email.strip().lower(),
            publishers=list(publishers),
            status="queued",
        ))


def update_job(job_id, status, result=None, error=None, started=False, finished=False):
    with session_scope() as session:
        job = session.get(ScrapingJob, job_id)
        if job is None:
            return False
        job.status = status
        job.result = result
        job.error = error[:4000] if error else None
        job.updated_at = utcnow()
        if started and job.started_at is None:
            job.started_at = utcnow()
        if finished:
            job.finished_at = utcnow()
        return True


def get_job(job_id):
    with SessionLocal() as session:
        job = session.get(ScrapingJob, job_id)
        if job is None:
            return None
        return {
            "job_id": job.id,
            "email": job.email,
            "publishers": job.publishers,
            "state": job.status,
            "result": job.result,
            "error": job.error,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }


def begin_email_delivery(idempotency_key, recipient):
    """Return False only when this exact job has already been marked sent."""
    with session_scope() as session:
        delivery = session.scalar(
            select(EmailDelivery).where(EmailDelivery.idempotency_key == idempotency_key)
        )
        if delivery is None:
            delivery = EmailDelivery(
                idempotency_key=idempotency_key,
                recipient=recipient.strip().lower(),
                status="sending",
            )
            session.add(delivery)
        elif delivery.status == "sent":
            return False
        else:
            delivery.status = "sending"
            delivery.error = None
            delivery.updated_at = utcnow()
    return True


def finish_email_delivery(idempotency_key, sent, error=None):
    with session_scope() as session:
        delivery = session.scalar(
            select(EmailDelivery).where(EmailDelivery.idempotency_key == idempotency_key)
        )
        if delivery is None:
            delivery = EmailDelivery(
                idempotency_key=idempotency_key,
                recipient="unknown",
                status="sent" if sent else "failed",
            )
            session.add(delivery)
        else:
            delivery.status = "sent" if sent else "failed"
            delivery.error = error[:4000] if error else None
            delivery.updated_at = utcnow()
        if sent:
            delivery.sent_at = utcnow()
