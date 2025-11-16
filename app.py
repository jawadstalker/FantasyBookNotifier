# app.py
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

    # simple summarization (English only)
    out = summarizer(text, max_length=130, min_length=30, do_sample=False)
    summary = out[0]['summary_text'].strip()
    return jsonify({"summary": summary})

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
