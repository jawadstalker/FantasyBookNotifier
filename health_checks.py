"""Operational health checks for API, Celery broker and worker."""
import os
import time

from flask import Blueprint, current_app, jsonify
from redis import Redis
from redis.exceptions import RedisError

from celery_app import celery_app

health_blueprint = Blueprint("operational_health", __name__)
STARTED_AT = time.monotonic()
WORKER_PING_TIMEOUT = float(os.getenv("WORKER_HEALTH_TIMEOUT", "1.5"))


def _check_redis():
    redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
    try:
        return {"status": "ok" if client.ping() else "error"}
    except RedisError:
        current_app.logger.exception("Redis health check failed")
        return {"status": "error"}
    finally:
        client.close()


def _check_celery_worker():
    try:
        replies = celery_app.control.ping(timeout=WORKER_PING_TIMEOUT, limit=1)
        if replies:
            worker = next(iter(replies))
            return {"status": "ok", "worker": worker}
        return {"status": "error", "reason": "no worker responded"}
    except Exception:
        current_app.logger.exception("Celery worker health check failed")
        return {"status": "error", "reason": "worker ping failed"}


@health_blueprint.get("/health/live")
def liveness():
    """Liveness only: confirms the Flask process can serve requests."""
    return jsonify({"status": "ok", "uptime_seconds": round(time.monotonic() - STARTED_AT, 2)})


@health_blueprint.get("/health/ready")
def readiness():
    """Readiness check for dependencies needed to process background jobs."""
    checks = {"redis": _check_redis(), "celery_worker": _check_celery_worker()}
    ready = all(check["status"] == "ok" for check in checks.values())
    return jsonify({"status": "ok" if ready else "degraded", "checks": checks}), (200 if ready else 503)
