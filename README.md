# FantasyBookNotifier

<img src="logo.png" alt="FantasyBookNotifier Banner" width="200"/>


## Overview

FantasyBookNotifier is a Flask-based web application that automates
fetching the latest books from Iranian and foreign publishers, extracts
character names from text in English and Persian, summarizes long
English texts, and provides book recommendations using TF‑IDF
similarity.
it could get a lot of cool features
This documentation explains all components, APIs, models, installation
steps, and usage instructions.
feel free to use it 
still working in other sides of it. 
## Features

-   Automatic book scraping from multiple publishers\
-   Email notifications\
-   Persian & English name extraction (Stanza + spaCy)\
-   English text summarization (BART large CNN)\
-   Book recommendation system using TF‑IDF\
-   RESTful API routes\
-   Multi-threaded scraping worker

## Tech Stack

-   **Backend:** Python, Flask\
-   **NLP:** spaCy, Stanza, Transformers (HuggingFace)\
-   **ML:** Scikit-learn (TF‑IDF + Cosine similarity)\
-   **Data:** Pandas\
-   **Async:** asyncio\
-   **Threading:** Python threading module

## Project Structure

    /project
    │── app.py
    │── books_scraper_full.py
    │── index.html
    │── Books.csv
    │── requirements.txt

## Installation

1.  Clone repository\
2.  Install python dependencies:


    pip install -r requirements.txt
    python -m spacy download en_core_web_sm
    python -c "import stanza; stanza.download('fa')"

3.  Ensure `Books.csv` is available in root directory.

4.  Run app:


    python app.py

## API Documentation

### 1. Extract Names

`POST /extract-names`

**Body:**

``` json
{"text": "your text here"}
```

**Response:**

``` json
{"names": ["Alice", "Bob"]}
```

------------------------------------------------------------------------

### 2. Summarize Text

`POST /summarize`

**Body:**

``` json
{"text": "long english text..."}
```

**Response:**

``` json
{"summary": "short version"}
```

------------------------------------------------------------------------

### 3. Book Recommender

`POST /recommend`

**Body:**

``` json
{"keywords": "magic wizard fantasy"}
```

**Response:**

``` json
{
  "recommendations": [
    {"title": "...", "author": "...", "publisher": "...", "score": 0.87}
  ]
}
```

------------------------------------------------------------------------

### 5. Check a scraping job

`GET /jobs/<job_id>`

The `POST /subscribe` response includes a `job_id` and a `status_url`. Poll this URL to see whether the job is pending, running, retrying, successful, or failed. Results expire after 24 hours; this endpoint is not a permanent job history.

### 4. Subscribe to Publishers

`POST /subscribe`

**Body:**

``` json
{
  "email": "user@example.com",
  "publishers": ["Amazon", "SomePublisher"]
}
```

------------------------------------------------------------------------

## NLP Components

### Persian NER

Uses **Stanza**\
Extracts proper Persian names (`pers` tag).

### English NER

Uses **spaCy (en_core_web_sm)**\
Extracts `PERSON` entities.

### Language Detection

`langdetect` library automatically routes text to correct pipeline.

------------------------------------------------------------------------

## Summarizer Model

Uses **facebook/bart-large-cnn**\
- max_length = 130\
- min_length = 30

------------------------------------------------------------------------

## Recommender System

1.  Loads Books.csv\
2.  Builds TF‑IDF vector for each book\
3.  Compares user keywords with cosine similarity\
4.  Returns top 3 matches

------------------------------------------------------------------------

## Threaded Scraper Worker

The `/subscribe` route starts a background thread: - runs asyncio
scraper\
- sends user email after scraping

------------------------------------------------------------------------
## 📦 Libraries & Documentation

| Library | Purpose | Documentation |
|---------|---------|---------------|
| Flask | Web framework / API | [Flask Docs](https://flask.palletsprojects.com/) |
| threading | Concurrent scraping | [threading Docs](https://docs.python.org/3/library/threading.html) |
| asyncio | Asynchronous tasks | [asyncio Docs](https://docs.python.org/3/library/asyncio.html) |
| os | Environment / path utilities | [os Docs](https://docs.python.org/3/library/os.html) |
| stanza | Persian NLP & Named Entity Recognition | [Stanza Docs](https://stanfordnlp.github.io/stanza/) |
| spacy | English NLP & Named Entity Recognition | [spaCy Docs](https://spacy.io/usage) |
| langdetect | Language detection | [langdetect Docs](https://pypi.org/project/langdetect/) |
| collections.Counter | Count & sort occurrences | [Counter Docs](https://docs.python.org/3/library/collections.html#collections.Counter) |
| transformers | Text summarization (HuggingFace) | [Transformers Docs](https://huggingface.co/docs/transformers/index) |
| pandas | Data manipulation / CSV | [pandas Docs](https://pandas.pydata.org/docs/) |
| sklearn.feature_extraction.text | TF-IDF vectorizer | [TF-IDF Docs](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) |
| sklearn.metrics.pairwise | Cosine similarity | [cosine_similarity Docs](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.cosine_similarity.html) |

## Running with Docker Compose

The API uses Celery and Redis for scraping jobs. For a local containerized setup:

1. Install Docker with Compose support.
2. Copy `.env.example` to `.env` and configure email settings.
3. Put `Books.csv` in the project root if you want recommendations (it is not stored in Git).
4. Run `docker compose up --build`.
5. Open `http://localhost:5000/health`; follow worker output with `docker compose logs -f worker`.

The initial image build downloads NLP models and may take several minutes. The web API, Redis broker and Celery worker run as separate services. Do not expose Redis directly to the public internet.

## Configuration and Deployment Notes

- Copy `.env.example` to `.env` and set email configuration using environment variables. Never commit real credentials.
- `FLASK_DEBUG` defaults to disabled. The default host is `127.0.0.1`; set `HOST=0.0.0.0` only when external/container access is required.
- The API limits request body size and NLP input length. `GET /health` reports whether the recommender catalogue loaded.
- `Books.csv` is local data and is excluded from Git. Set `BOOKS_CSV_PATH` if the file lives elsewhere.
- For production, use a WSGI server and move scraping jobs to a durable queue; the current background thread can be lost if the process stops.
- See [the production checklist](docs/production-checklist.md) for remaining deployment work.
- Set a custom port via environment:


    PORT=8000 python app.py

------------------------------------------------------------------------

## License

MIT License

## Author

Jawad Stalker
 I will add some cool website for the feature 
