import os
import time
import threading
from flask import Flask, jsonify, request, send_from_directory
import nltk
from nlp_analyzer import get_trends

# Initialize Flask app
# Static folder points to the frontend directory next to backend
app = Flask(__name__, static_folder='../frontend', static_url_path='')

# Global cache
TRENDS_CACHE = {
    'en': [],
    'ko': []
}
LAST_UPDATED = {
    'en': None,
    'ko': None
}
CACHE_LOCK = threading.Lock()

def download_nltk_resources():
    """
    Downloads required NLTK resources if not already present.
    """
    resources = ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words', 'stopwords']
    for resource in resources:
        try:
            # We try to load it to check if it exists, otherwise download it
            if resource == 'punkt':
                nltk.data.find('tokenizers/punkt')
            elif resource == 'stopwords':
                nltk.data.find('corpora/stopwords')
            elif resource == 'averaged_perceptron_tagger':
                nltk.data.find('taggers/averaged_perceptron_tagger')
            elif resource == 'maxent_ne_chunker':
                nltk.data.find('chunkers/maxent_ne_chunker')
            elif resource == 'words':
                nltk.data.find('corpora/words')
        except LookupError:
            print(f"Downloading NLTK resource: {resource}...")
            nltk.download(resource, quiet=True)
            print(f"Finished downloading {resource}.")

def fetch_and_cache_all():
    """
    Fetches trends for all languages and stores them in the global cache.
    """
    print("Updating news trends cache in background...")
    for lang in ['en', 'ko']:
        try:
            start_time = time.time()
            data = get_trends(lang)
            with CACHE_LOCK:
                TRENDS_CACHE[lang] = data
                LAST_UPDATED[lang] = time.time()
            duration = time.time() - start_time
            print(f"[{lang}] Trends updated successfully in {duration:.2f}s ({len(data)} keywords).")
        except Exception as e:
            print(f"[{lang}] Error updating trends: {e}")

def background_scheduler():
    """
    Background worker thread that updates the cache every 10 minutes.
    """
    # First update on startup
    fetch_and_cache_all()
    
    while True:
        # Sleep for 10 minutes (600 seconds)
        time.sleep(600)
        fetch_and_cache_all()

@app.route('/')
def serve_index():
    """Serves the index.html file."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serves static files (styles.css, app.js, images, etc.) from the frontend directory."""
    return send_from_directory(app.static_folder, path)

@app.route('/api/trends', methods=['GET'])
def api_trends():
    """
    Returns the list of processed trends.
    Query parameters:
    - lang: 'en' or 'ko' (default: 'en')
    """
    lang = request.args.get('lang', 'en')
    if lang not in ['en', 'ko']:
        return jsonify({'error': 'Unsupported language. Choose "en" or "ko".'}), 400
        
    with CACHE_LOCK:
        data = TRENDS_CACHE.get(lang, [])
        last_updated = LAST_UPDATED.get(lang)
        
    # If the cache is empty (e.g. background thread hasn't finished its first run yet),
    # fetch synchronously to avoid sending empty data on first load.
    if not data:
        try:
            print(f"Cache miss for '{lang}'. Fetching synchronously...")
            data = get_trends(lang)
            with CACHE_LOCK:
                TRENDS_CACHE[lang] = data
                last_updated = time.time()
                LAST_UPDATED[lang] = last_updated
        except Exception as e:
            return jsonify({'error': f'Failed to fetch trends: {str(e)}'}), 500
            
    return jsonify({
        'language': lang,
        'last_updated': last_updated,
        'count': len(data),
        'trends': data
    })

@app.route('/api/status', methods=['GET'])
def api_status():
    """
    Returns API status, including update times and durations.
    """
    with CACHE_LOCK:
        status_info = {
            'status': 'healthy',
            'last_updated_en': LAST_UPDATED['en'],
            'last_updated_ko': LAST_UPDATED['ko'],
            'next_update_en_in_seconds': max(0, 600 - (time.time() - LAST_UPDATED['en'])) if LAST_UPDATED['en'] else None,
            'next_update_ko_in_seconds': max(0, 600 - (time.time() - LAST_UPDATED['ko'])) if LAST_UPDATED['ko'] else None,
        }
    return jsonify(status_info)

if __name__ == '__main__':
    # Ensure NLTK resources are available
    download_nltk_resources()
    
    # Start the background crawler thread
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run the Flask web app
    # Port 5000 is standard
    print("Starting Flask application on http://localhost:5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)
