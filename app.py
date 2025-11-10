# app.py
# Simple Flask app to serve the form and start scraping jobs.
# Place this file in the same folder as books_scraper_full.py and index.html.

from flask import Flask, request, jsonify, send_from_directory
import threading
import asyncio
import os

# Import the scraper module (books_scraper_full.py must be in the same directory)
import books_scraper_full as scraper

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/publishers')
def get_publishers():
    # Return the list of publisher keys from the SCRAPERS_MAP
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Ensure environment variables or constants in books_scraper_full.py are configured
    app.run(host='0.0.0.0', port=port, debug=True)
