"""Flask API contract tests without loading large NLP models or external services."""
import importlib
import sys
import types

import pytest


def _module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def _install_lightweight_import_stubs(monkeypatch):
    # The application loads several multi-hundred-megabyte models at import
    # time. Stub these dependencies so route tests remain fast and offline.
    scraper = _module(
        "books_scraper_full",
        SCRAPERS_MAP={"Publisher A": object(), "Publisher B": object()},
    )
    monkeypatch.setitem(sys.modules, "books_scraper_full", scraper)

    celery_pkg = _module("celery")
    celery_pkg.__path__ = []
    celery_result = _module("celery.result", AsyncResult=type("AsyncResult", (), {}))
    monkeypatch.setitem(sys.modules, "celery", celery_pkg)
    monkeypatch.setitem(sys.modules, "celery.result", celery_result)

    class FakeTask:
        def __init__(self):
            self.calls = []

        def apply_async(self, **kwargs):
            self.calls.append(kwargs)

    fake_task = FakeTask()
    monkeypatch.setitem(sys.modules, "celery_app", _module("celery_app", celery_app=object()))
    monkeypatch.setitem(sys.modules, "tasks", _module("tasks", scrape_publishers_task=fake_task))

    class FakePipeline:
        def __call__(self, text, **kwargs):
            return [{"summary_text": "test summary"}]

    class FakeLoader:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            return object()

    monkeypatch.setitem(sys.modules, "stanza", _module("stanza", Pipeline=lambda *_a, **_k: lambda _text: None))
    monkeypatch.setitem(sys.modules, "spacy", _module("spacy", load=lambda *_a, **_k: lambda _text: None))
    monkeypatch.setitem(
        sys.modules,
        "langdetect",
        _module("langdetect", detect=lambda _text: "en", LangDetectException=type("LangDetectException", (Exception,), {})),
    )
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        _module(
            "transformers",
            pipeline=lambda *_a, **_k: FakePipeline(),
            AutoTokenizer=FakeLoader,
            AutoModelForSeq2SeqLM=FakeLoader,
        ),
    )

    class FakePandas:
        @staticmethod
        def read_csv(*_args, **_kwargs):
            raise FileNotFoundError("test intentionally does not load the book catalogue")

    monkeypatch.setitem(sys.modules, "pandas", _module("pandas", read_csv=FakePandas.read_csv))

    class FakeTfidfVectorizer:
        def __init__(self, **_kwargs):
            pass

    feature_extraction = _module("sklearn.feature_extraction")
    feature_extraction.__path__ = []
    text_module = _module("sklearn.feature_extraction.text", TfidfVectorizer=FakeTfidfVectorizer)
    sklearn = _module("sklearn")
    sklearn.__path__ = []
    metrics = _module("sklearn.metrics")
    metrics.__path__ = []
    pairwise = _module("sklearn.metrics.pairwise", cosine_similarity=lambda *_a, **_k: [])
    monkeypatch.setitem(sys.modules, "sklearn", sklearn)
    monkeypatch.setitem(sys.modules, "sklearn.feature_extraction", feature_extraction)
    monkeypatch.setitem(sys.modules, "sklearn.feature_extraction.text", text_module)
    monkeypatch.setitem(sys.modules, "sklearn.metrics", metrics)
    monkeypatch.setitem(sys.modules, "sklearn.metrics.pairwise", pairwise)
    return fake_task


@pytest.fixture()
def api(monkeypatch):
    # Force a clean import so dependency stubs are installed before app imports.
    sys.modules.pop("app", None)
    fake_task = _install_lightweight_import_stubs(monkeypatch)
    import app as flask_app

    flask_app.app.config.update(TESTING=True)
    with flask_app.app.test_client() as client:
        yield flask_app, client, fake_task
    sys.modules.pop("app", None)


def test_publishers_endpoint_lists_supported_publishers(api):
    _flask_app, client, _task = api
    response = client.get("/publishers")
    assert response.status_code == 200
    assert response.get_json() == {"publishers": ["Publisher A", "Publisher B"]}


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"email": "not-an-email", "publishers": ["Publisher A"]},
        {"email": "reader@example.com", "publishers": []},
        {"email": "reader@example.com", "publishers": ["Unknown Publisher"]},
        {"email": "reader@example.com", "publishers": [1]},
    ],
)
def test_subscribe_rejects_invalid_payloads(api, payload):
    _flask_app, client, task = api
    response = client.post("/subscribe", json=payload) if payload is not None else client.post(
        "/subscribe", data="not-json", content_type="text/plain"
    )
    assert response.status_code == 400
    assert task.calls == []


def test_subscribe_persists_and_enqueues_valid_request(api, monkeypatch):
    flask_app, client, task = api
    saved = {}
    monkeypatch.setattr(flask_app, "upsert_subscription", lambda email, publishers: saved.update(email=email, publishers=publishers))
    monkeypatch.setattr(flask_app, "create_job", lambda job_id, email, publishers: saved.update(job_id=job_id))
    response = client.post(
        "/subscribe",
        json={"email": " Reader@Example.com ", "publishers": ["Publisher A", "Publisher A"]},
    )

    assert response.status_code == 202
    body = response.get_json()
    assert body["message"] == "scraping job queued"
    assert saved["email"] == "reader@example.com"
    assert saved["publishers"] == ["Publisher A"]
    assert saved["job_id"] == body["job_id"]
    assert task.calls == [{
        "args": [["Publisher A"], "reader@example.com"],
        "task_id": body["job_id"],
    }]


def test_subscribe_returns_service_unavailable_when_queue_fails(api, monkeypatch):
    flask_app, client, _task = api
    monkeypatch.setattr(flask_app, "upsert_subscription", lambda *_args: None)
    monkeypatch.setattr(flask_app, "create_job", lambda *_args: None)

    def fail_enqueue(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(flask_app.scrape_publishers_task, "apply_async", fail_enqueue)
    monkeypatch.setattr(flask_app, "update_job", lambda *_args, **_kwargs: None)
    response = client.post(
        "/subscribe",
        json={"email": "reader@example.com", "publishers": ["Publisher A"]},
    )
    assert response.status_code == 503
    assert response.get_json()["error"] == "scraping queue is unavailable"


def test_job_status_returns_persisted_job(api, monkeypatch):
    flask_app, client, _task = api
    monkeypatch.setattr(
        flask_app,
        "get_persisted_job",
        lambda _job_id: {
            "job_id": "12345678-1234-1234-1234-123456789abc",
            "state": "completed",
            "publishers": ["Publisher A"],
            "created_at": "2026-10-26T10:00:00+00:00",
            "started_at": "2026-10-26T10:00:01+00:00",
            "finished_at": "2026-10-26T10:00:02+00:00",
            "result": {"message": "done"},
            "error": None,
        },
    )
    response = client.get("/jobs/12345678-1234-1234-1234-123456789abc")
    assert response.status_code == 200
    assert response.get_json()["state"] == "completed"
    assert response.get_json()["result"] == {"message": "done"}


def test_job_status_distinguishes_invalid_and_missing_ids(api, monkeypatch):
    flask_app, client, _task = api
    missing = client.get("/jobs/not-a-uuid")
    assert missing.status_code == 400

    monkeypatch.setattr(flask_app, "get_persisted_job", lambda _job_id: None)
    unknown = client.get("/jobs/12345678-1234-1234-1234-123456789abc")
    assert unknown.status_code == 404



def test_liveness_endpoint_is_independent_of_dependencies(api):
    _flask_app, client, _task = api
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["uptime_seconds"] >= 0


def test_readiness_endpoint_reports_dependency_failure(api, monkeypatch):
    flask_app, client, _task = api
    import health_checks

    monkeypatch.setattr(health_checks, "_check_redis", lambda: {"status": "ok"})
    monkeypatch.setattr(
        health_checks, "_check_celery_worker",
        lambda: {"status": "error", "reason": "no worker responded"},
    )
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"]["status"] == "ok"
    assert body["checks"]["celery_worker"]["status"] == "error"


def test_readiness_endpoint_returns_200_when_dependencies_are_healthy(api, monkeypatch):
    _flask_app, client, _task = api
    import health_checks

    monkeypatch.setattr(health_checks, "_check_redis", lambda: {"status": "ok"})
    monkeypatch.setattr(
        health_checks, "_check_celery_worker",
        lambda: {"status": "ok", "worker": "celery@integration"},
    )
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
