from flask import Flask, request, jsonify, send_from_directory
import logging
import os
import re
from pathlib import Path

import books_scraper_full as scraper
from celery.result import AsyncResult
from celery_app import celery_app
from tasks import scrape_publishers_task
import stanza
import spacy
from langdetect import detect, LangDetectException
from collections import Counter
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parent
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(1 * 1024 * 1024)))
MAX_NLP_TEXT_CHARS = int(os.getenv("MAX_NLP_TEXT_CHARS", "20000"))
MAX_RECOMMENDATION_KEYWORDS_CHARS = int(os.getenv("MAX_RECOMMENDATION_KEYWORDS_CHARS", "1000"))

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({"error": "request body is too large"}), 413


@app.errorhandler(400)
def bad_request(_error):
    return jsonify({"error": "invalid request"}), 400


def get_json_payload():
    """Return a JSON object, rejecting arrays, scalars and malformed JSON."""
    if not request.is_json:
        return None
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def get_text_field(data, field, max_chars):
    value = data.get(field)
    if not isinstance(value, str):
        return None, f"{field} must be a string"
    value = value.strip()
    if not value:
        return None, f"{field} is required"
    if len(value) > max_chars:
        return None, f"{field} must be at most {max_chars} characters"
    return value, None


# Load NLP models at startup. These models are large; for constrained deployments,
# run the API with a single worker or move inference into a dedicated worker service.
logger.info("Loading Persian model (Stanza)...")
fa_nlp = stanza.Pipeline("fa", processors="tokenize,ner", verbose=False)

logger.info("Loading English model (spaCy)...")
en_nlp = spacy.load("en_core_web_sm")

logger.info("Loading English summarization model...")
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "facebook/bart-large-cnn")
tokenizer = AutoTokenizer.from_pretrained(SUMMARIZER_MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(SUMMARIZER_MODEL)
summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=-1)

# Load the catalogue relative to this file, rather than the shell's current directory.
BOOKS_CSV_PATH = Path(os.getenv("BOOKS_CSV_PATH", str(BASE_DIR / "Books.csv")))

try:
    books_df = pd.read_csv(
        BOOKS_CSV_PATH,
        on_bad_lines="skip",
        encoding="latin-1",
        low_memory=False,
        dtype=str,
    )
    required_columns = ["Book-Title", "Book-Author", "Publisher"]
    missing_columns = [column for column in required_columns if column not in books_df.columns]
    if missing_columns:
        raise ValueError(f"Books dataset is missing columns: {', '.join(missing_columns)}")

    books_df = books_df[required_columns].dropna().drop_duplicates()
    for column in required_columns:
        books_df[column] = books_df[column].astype(str).str.strip()
    books_df = books_df[
        (books_df["Book-Title"] != "")
        & (books_df["Book-Author"] != "")
        & (books_df["Publisher"] != "")
    ].reset_index(drop=True)
    books_df["description"] = (
        books_df["Book-Title"] + " " + books_df["Book-Author"] + " " + books_df["Publisher"]
    )

    tfidf = TfidfVectorizer(stop_words="english", max_features=200000)
    tfidf_matrix = tfidf.fit_transform(books_df["description"])
    logger.info("Book recommender loaded: %s", tfidf_matrix.shape)
except Exception:
    logger.exception("Book recommender could not load dataset %s", BOOKS_CSV_PATH)
    books_df = None
    tfidf = None
    tfidf_matrix = None


def extract_persian_names(text):
    doc = fa_nlp(text)
    return sorted({
        ent.text.strip()
        for ent in doc.ents
        if ent.type == "pers" and ent.text.strip()
    })


def extract_english_names(text):
    doc = en_nlp(text)
    persons = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON" and ent.text.strip()]
    counted = Counter(persons)
    return [name for name, _ in counted.most_common()]


def extract_names_general(text):
    try:
        lang = detect(text)
    except LangDetectException:
        return []

    if lang == "fa":
        return extract_persian_names(text)
    if lang == "en":
        return extract_english_names(text)
    return []


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "recommender_available": books_df is not None and tfidf_matrix is not None,
    })


@app.route("/extract-names", methods=["POST"])
def extract_names_api():
    data = get_json_payload()
    if data is None:
        return jsonify({"error": "a JSON object is required"}), 400
    text, error = get_text_field(data, "text", MAX_NLP_TEXT_CHARS)
    if error:
        return jsonify({"error": error}), 400
    try:
        return jsonify({"names": extract_names_general(text)})
    except Exception:
        logger.exception("Name extraction failed")
        return jsonify({"error": "name extraction failed"}), 500


@app.route("/summarize", methods=["POST"])
def summarize_api():
    data = get_json_payload()
    if data is None:
        return jsonify({"error": "a JSON object is required"}), 400
    text, error = get_text_field(data, "text", MAX_NLP_TEXT_CHARS)
    if error:
        return jsonify({"error": error}), 400
    try:
        out = summarizer(
            text,
            max_length=130,
            min_length=30,
            do_sample=False,
            truncation=True,
        )
        return jsonify({"summary": out[0]["summary_text"].strip()})
    except Exception:
        logger.exception("Text summarization failed")
        return jsonify({"error": "summarization failed"}), 500


@app.route("/recommend", methods=["POST"])
def recommend_books_api():
    if books_df is None or tfidf is None or tfidf_matrix is None:
        return jsonify({"error": "book recommender is not available"}), 503

    data = get_json_payload()
    if data is None:
        return jsonify({"error": "a JSON object is required"}), 400
    keywords, error = get_text_field(data, "keywords", MAX_RECOMMENDATION_KEYWORDS_CHARS)
    if error:
        return jsonify({"error": error}), 400

    try:
        user_vec = tfidf.transform([keywords])
        similarities = cosine_similarity(user_vec, tfidf_matrix).flatten()
        positive_indices = similarities.argsort()[::-1]
        results = []
        seen_titles = set()
        for idx in positive_indices:
            score = float(similarities[idx])
            if score <= 0:
                break
            book = books_df.iloc[idx]
            title_key = book["Book-Title"].casefold()
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)
            results.append({
                "title": book["Book-Title"],
                "author": book["Book-Author"],
                "publisher": book["Publisher"],
                "score": score,
            })
            if len(results) == 3:
                break
        return jsonify({"recommendations": results})
    except Exception:
        logger.exception("Book recommendation failed")
        return jsonify({"error": "book recommendation failed"}), 500


@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "index.html")


@app.route("/publishers")
def get_publishers():
    return jsonify({"publishers": sorted(scraper.SCRAPERS_MAP.keys())})


@app.route("/subscribe", methods=["POST"])
def subscribe():
    data = get_json_payload()
    if data is None:
        return jsonify({"error": "a JSON object is required"}), 400

    email = data.get("email")
    publishers = data.get("publishers")
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "email is required"}), 400
    email = email.strip()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify({"error": "a valid email address is required"}), 400
    if not isinstance(publishers, list) or not publishers:
        return jsonify({"error": "select at least one publisher"}), 400
    if any(not isinstance(publisher, str) for publisher in publishers):
        return jsonify({"error": "publishers must be a list of publisher names"}), 400

    allowed_publishers = set(scraper.SCRAPERS_MAP.keys())
    unknown_publishers = sorted(set(publishers) - allowed_publishers)
    if unknown_publishers:
        return jsonify({
            "error": "unknown publisher(s)",
            "publishers": unknown_publishers,
        }), 400
    publishers = list(dict.fromkeys(publishers))

    try:
        job = scrape_publishers_task.delay(publishers, email)
    except Exception:
        logger.exception("Could not enqueue scraping job")
        return jsonify({"error": "scraping queue is unavailable"}), 503

    return jsonify({
        "message": "scraping job queued",
        "job_id": job.id,
        "status_url": f"/jobs/{job.id}",
        "publishers": publishers,
    }), 202


@app.route("/jobs/<task_id>", methods=["GET"])
def get_scraping_job(task_id):
    # Celery's default task identifiers are UUIDs. Reject malformed IDs early.
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", task_id):
        return jsonify({"error": "invalid job id"}), 400

    job = AsyncResult(task_id, app=celery_app)
    response = {"job_id": task_id, "state": job.state.lower()}
    if job.state == "SUCCESS":
        result = job.result if isinstance(job.result, dict) else {}
        response["result"] = {
            "message": result.get("message", "scraping completed"),
            "publishers": result.get("publishers", []),
        }
    elif job.state == "FAILURE":
        logger.error("Scraping job %s failed: %s", task_id, job.result)
        response["error"] = "scraping job failed; check worker logs"
    elif job.state == "RETRY":
        response["message"] = "job will be retried after a transient failure"
    elif job.state in {"PENDING", "STARTED", "RECEIVED"}:
        response["message"] = "job is queued or running"
    return jsonify(response), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=port, debug=debug)
