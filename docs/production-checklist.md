# Production Readiness Checklist

## Included in this branch

- API request bodies are size-limited and JSON payloads are validated.
- NLP text and recommendation keyword lengths have explicit limits.
- Publisher names are checked against the scraper registry before starting a job.
- Scraper email credentials are read from environment variables instead of source code.
- Flask debug mode is off by default and the default bind address is localhost.
- The book CSV path is resolved independently of the process working directory.
- The recommender drops duplicate rows, ignores empty catalogue records, and does not return zero-score matches.
- A lightweight `GET /health` endpoint reports whether the recommender catalogue loaded.
- Python caches, environment files, generated images and local datasets are ignored by Git.

## Before deploying publicly

1. Set `HOST=0.0.0.0` only when the service must be reachable outside the host/container.
2. Set `SENDER_EMAIL`, `APP_PASSWORD`, and `RECEIVER_EMAIL` in the deployment secret store. Do not put secrets in Git.
3. Install the spaCy English model with `python -m spacy download en_core_web_sm` and download the Stanza Persian model during image/build setup with `python -c "import stanza; stanza.download('fa')"`.
4. Make sure `Books.csv` exists at `BOOKS_CSV_PATH` or mount it as deployment data. It is intentionally not tracked by Git.
5. Run behind a production WSGI server (for example, Gunicorn) and a reverse proxy with TLS. Do not use Flask's development server in production.
6. Scraping is queued through Celery and Redis; start the services with Docker Compose and keep Redis on a private network.
7. This branch persists subscriptions, scraping job state, and email-delivery records in SQLAlchemy. SQLite is suitable for local/small single-worker deployments; use PostgreSQL for higher concurrency and production workloads.
8. Add per-IP rate limiting, monitoring, alerting, and a deployment-specific concurrency policy for the large NLP models.
9. Review each publisher's terms, robots policy, image rights, and acceptable request frequency.
10. Run tests and a staging smoke test with real model files and a small sample catalogue before release.

## Persistent job history and delivery records

The `subscriptions`, `scraping_jobs`, and `email_deliveries` tables are managed by Alembic migrations. Docker Compose runs `alembic upgrade head` before starting the web service. The initial migration checks for existing tables and indexes so databases previously initialized with SQLAlchemy `create_all()` can be adopted without recreating those tables; verify the old schema matches before upgrading. For manual deployments, run the migration command before starting the API or worker. Set `DATABASE_URL` to use PostgreSQL or another SQLAlchemy-supported database. Docker Compose mounts `./data` into both the web and worker containers so the SQLite database survives container recreation.

`GET /jobs/<job_id>` reads job state from the database, including timestamps and stored results. Celery's result backend is still useful for worker internals, but it is no longer the source of truth for the public job status.

Email delivery uses a unique key per scraping job and records pending/sending/sent/failed states. SMTP does not support a transaction shared with the database: if a worker crashes after the mail server accepts an email but before the database records success, a retry can still send a duplicate. The record greatly improves observability and skips known-successful deliveries, but does not guarantee exactly-once delivery.

SQLite is not recommended for multiple web/worker hosts or high write concurrency. Use PostgreSQL and proper migrations before scaling horizontally.

## Important limitations

- The recommendation catalogue currently uses only title, author and publisher fields. It is a lexical baseline, not personalized or semantic recommendation.
- NLP models load during application startup, so the process requires significant memory and may take time to become ready.
- `/subscribe` returns HTTP 202 after enqueueing a Celery task. Delivery can still fail after retries; inspect persistent job status and worker logs.


## Running the queue locally

1. Install Docker Compose and make sure the local `Books.csv` file is present if you want recommendations.
2. Copy `.env.example` to `.env` and configure email credentials.
3. Start the services with `docker compose up --build`. The first build downloads large NLP model assets and may take a while.
4. Open `http://localhost:5000/health`. The web API and Celery worker are separate containers; Redis is the broker/result backend.
5. Submit `POST /subscribe` with a JSON object containing `email` and a list of valid `publishers`. The response includes `job_id` and `status_url`; poll `GET /jobs/<job_id>` to inspect state.
6. Use `docker compose logs -f worker` to inspect task progress and errors.

The public job status endpoint reads the SQL database, not the expiring Celery result backend. Do not expose Redis publicly.


## Database migrations

- The initial migration is `migrations/versions/0001_initial_persistent_records.py`.
- Review migrations before deploying them; take a database backup first.
- Apply changes with `alembic upgrade head`; inspect current revision with `alembic current`.
- If upgrading a database created by an earlier version that already created these tables with SQLAlchemy `create_all`, back it up and verify the existing schema matches the initial migration before upgrading.
- Test both migration and rollback paths against a disposable database. Do not run destructive downgrades against production without a reviewed recovery plan.


## Runtime health and troubleshooting

- `GET /health/live` is a lightweight liveness probe. It reports whether the Flask process is serving requests and includes process uptime; it intentionally does not require Redis or Celery.
- `GET /health/ready` checks Redis connectivity and waits briefly for a Celery worker ping. It returns HTTP 200 only when both dependencies respond, otherwise HTTP 503 with per-dependency status. Keep this endpoint internal or protect it if exposing dependency topology is undesirable.
- Docker Compose uses the liveness endpoint for the web container and Celery's `inspect ping` for the worker container. A container healthcheck is diagnostic; it does not automatically restart a process unless an orchestrator is configured to act on health status.
- Set `LOG_LEVEL=INFO` by default and use `LOG_LEVEL=DEBUG` only during controlled troubleshooting. Logs should be shipped to a centralized destination with retention and alerting configured by the deployment platform.
- If readiness is degraded, first inspect `docker compose ps` and `docker compose logs redis worker web`. Verify `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` are consistent across the web and worker containers.
