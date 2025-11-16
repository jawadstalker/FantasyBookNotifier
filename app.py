from flask import Flask, request, jsonify, send_from_directory
import threading
import asyncio
import os

# Existing import
import books_scraper_full as scraper

# --- NEW imports for Name Extraction ---
import stanza
import spacy
from langdetect import detect
from collections import Counter

# --- NEW imports for Summarization ---
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

# --- NEW imports for Book Recommender ---
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------
# Flask app
# ---------------------------
app = Flask(__name__, static_folder='.', static_url_path='')

# ---------------------------
# Load NER Models
# ---------------------------
print("Loading Persian model (Stanza)...")
fa_nlp = stanza.Pipeline('fa')

print("Loading English model (spaCy)...")
en_nlp = spacy.load("en_core_web_sm")

# ---------------------------
# Load Summarization Model
# ---------------------------
print("Loading English summarization model...")
SUMMARIZER_MODEL = "facebook/bart-large-cnn"
tokenizer = AutoTokenizer.from_pretrained(SUMMARIZER_MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(SUMMARIZER_MODEL)
summarizer = pipeline("summarization", model=model, tokenizer=tokenizer, device=-1)

# ---------------------------
# Load Books Dataset for Recommender
# ---------------------------
BOOKS_CSV_PATH = "Books.csv"  # حتما مسیر درست بدهید

try:
    books_df = pd.read_csv(BOOKS_CSV_PATH, on_bad_lines="skip", encoding="latin-1", low_memory=False, dtype=str)
    books_df = books_df[["Book-Title", "Book-Author", "Publisher"]].dropna()
    books_df["description"] = (
        books_df["Book-Title"].astype(str) + " " +
        books_df["Book-Author"].astype(str) + " " +
        books_df["Publisher"].astype(str)
    )

    tfidf = TfidfVectorizer(stop_words="english")
    tfidf_matrix = tfidf.fit_transform(books_df["description"])
    print("Book recommender TF-IDF model loaded. Matrix shape:", tfidf_matrix.shape)
except Exception as e:
    print("Error loading book recommender:", e)
    books_df = None
    tfidf_matrix = None

# ---------------------------
# Persian Name Extractor
# ---------------------------
def extract_persian_names(text):
    doc = fa_nlp(text)
    names = set()
    for ent in doc.ents:
        if ent.type == 'pers':
            name = ent.text.split()[0]
            names.add(name)
    return list(names)

# ---------------------------
# English Name Extractor
# ---------------------------
def extract_english_names(text):
    doc = en_nlp(text)
    persons = [ent.text.strip() for ent in doc.ents if ent.label_ == "PERSON"]
    counted = Counter(persons)
    return [name for name, _ in counted.most_common()]

# ---------------------------
# Language Detection Router
# ---------------------------
def extract_names_general(text):
    try:
        lang = detect(text)
    except:
        lang = "unknown"

    if lang == "fa":
        return extract_persian_names(text)
    elif lang == "en":
        return extract_english_names(text)
    else:
        return []

# ---------------------------
# API: Extract Names
# ---------------------------
@app.route('/extract-names', methods=['POST'])
def extract_names_api():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    names = extract_names_general(text)
    return jsonify({"names": names})

# ---------------------------
# API: Summarize Text
# ---------------------------
@app.route('/summarize', methods=['POST'])
def summarize_api():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    out = summarizer(text, max_length=130, min_length=30, do_sample=False)
    summary = out[0]['summary_text'].strip()
    return jsonify({"summary": summary})

# ---------------------------
# API: Book Recommender
# ---------------------------
@app.route("/recommend", methods=["POST"])
def recommend_books_api():
    if books_df is None or tfidf_matrix is None:
        return jsonify({"error": "Book recommender not available"}), 500

    data = request.get_json() or {}
    keywords = data.get("keywords", "").strip()
    if not keywords:
        return jsonify({"error": "keywords are required"}), 400

    user_vec = tfidf.transform([keywords])
    similarities = cosine_similarity(user_vec, tfidf_matrix).flatten()
    top_indices = similarities.argsort()[-3:][::-1]

    results = []
    for idx in top_indices:
        book = books_df.iloc[idx]
        results.append({
            "title": book["Book-Title"],
            "author": book["Book-Author"],
            "publisher": book["Publisher"],
            "score": float(similarities[idx])
        })

    return jsonify({"recommendations": results})

# ---------------------------
# Existing Routes
# ---------------------------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/publishers')
def get_publishers():
    pub_list = list(scraper.SCRAPERS_MAP.keys())
    return jsonify({"publishers": pub_list})

@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json() or {}
    email = data.get('email')
    publishers = data.get('publishers', [])
    if not email:
        return jsonify({"error": "email required"}), 400
    if not publishers:
        return jsonify({"error": "please select at least one publisher"}), 400

    def worker(e, pubs):
        try:
            print(f"[Worker] Starting scraping for {e} -> {pubs}")
            asyncio.run(scraper.run_for(pubs, e))
            print("[Worker] Worker finished")
        except Exception as exc:
            print("[Worker] exception:", exc)

    t = threading.Thread(target=worker, args=(email, publishers), daemon=True)
    t.start()
    return jsonify({"message": "Subscription accepted. Scraping started."}), 200

# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
