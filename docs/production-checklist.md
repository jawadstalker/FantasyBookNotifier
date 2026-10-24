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
6. Move scraping to a durable task queue (Celery/RQ plus Redis) before relying on it for important notifications. The current daemon thread is intentionally a small-deployment bridge; jobs can be lost when the process exits and there is no status endpoint.
7. Add persistent storage for books, subscriptions and job history before enabling accounts or scheduled notifications.
8. Add per-IP rate limiting, monitoring, alerting, and a deployment-specific concurrency policy for the large NLP models.
9. Review each publisher's terms, robots policy, image rights, and acceptable request frequency.
10. Run tests and a staging smoke test with real model files and a small sample catalogue before release.

## Important limitations

- The recommendation catalogue currently uses only title, author and publisher fields. It is a lexical baseline, not personalized or semantic recommendation.
- NLP models load during application startup, so the process requires significant memory and may take time to become ready.
- `/subscribe` currently returns HTTP 202 after starting an in-process daemon thread; it does not guarantee that scraping or email delivery will complete.


## Running the queue locally

1. Install Docker Compose and make sure the local `Books.csv` file is present if you want recommendations.
2. Copy `.env.example` to `.env` and configure email credentials.
3. Start the services with `docker compose up --build`. The first build downloads large NLP model assets and may take a while.
4. Open `http://localhost:5000/health`. The web API and Celery worker are separate containers; Redis is the broker/result backend.
5. Submit `POST /subscribe` with a JSON object containing `email` and a list of valid `publishers`. The response includes `job_id` and `status_url`; poll `GET /jobs/<job_id>` to inspect state.
6. Use `docker compose logs -f worker` to inspect task progress and errors.

The job status endpoint uses Celery's expiring result backend, so it is not a permanent job-history system. A later phase should persist jobs and subscriptions in a database. Do not expose Redis publicly.
