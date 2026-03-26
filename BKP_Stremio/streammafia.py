from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

app = Flask(__name__)
CORS(app)  # Enable CORS for Stremio

TMDB_API_KEY = "ea7b1fc3807d8a53d4227a80a15aeed1"

def decrypt_payload(payload_json):
    """Decrypts the autoembed.in payload."""
    try:
        iv = base64.b64decode(payload_json["iv"])
        tag = base64.b64decode(payload_json["tag"])
        data = base64.b64decode(payload_json["data"])

        password = b"uA8&vN3$pL9@kX4#jW"
        key = hashlib.sha256(password).digest()
        ciphertext = data + tag

        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return json.loads(decrypted.decode('utf-8'))
    except Exception as e:
        print(f"Decryption error: {e}")
        return None

def get_tmdb_id(imdb_id):
    """Converts IMDb ID to TMDB ID."""
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    resp = requests.get(url).json()
    
    if "movie_results" in resp and resp["movie_results"]:
        return resp["movie_results"][0]["id"], "movie"
    elif "tv_results" in resp and resp["tv_results"]:
        return resp["tv_results"][0]["id"], "tv"
    return None, None

def get_streams(imdb_id):
    """Fetches and builds streams for Stremio."""
    # Handle optional Stremio format like tt123456:1:2 for series
    is_series = False
    season, episode = None, None
    if ":" in imdb_id:
        parts = imdb_id.split(":")
        imdb_id = parts[0]
        season = parts[1]
        episode = parts[2]
        is_series = True

    tmdb_id, media_type = get_tmdb_id(imdb_id)
    if not tmdb_id:
        return []

    # If it's a TV show, we need the tv show type
    if is_series:
        autoembed_url = f"https://autoembed.in/downloads/?type=tv&id={tmdb_id}&season={season}&episode={episode}"
    else:
        autoembed_url = f"https://autoembed.in/downloads/?type=movie&id={tmdb_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://dl.streammafia.to/"
    }

    try:
        resp = requests.get(autoembed_url, headers=headers).json()
        decrypted = decrypt_payload(resp)
        if not decrypted or "cdn_response" not in decrypted:
            return []
            
        stremio_streams = []
        data_list = decrypted["cdn_response"].get("data", [])
        
        for item in data_list:
            lang = item.get("parsed_lang_name", "Unknown")
            streams_obj = item.get("stream", {})
            
            # Add HLS stream if available
            if "hls_streaming" in streams_obj and streams_obj["hls_streaming"]:
                stremio_streams.append({
                    "name": "StreamMafia",
                    "title": f"Auto | {lang}",
                    "url": streams_obj["hls_streaming"]
                })
                
            # Add Direct Downloads grouped by quality
            downloads = streams_obj.get("download", [])
            for dl in downloads:
                quality = dl.get("quality", "Unknown")
                dl_url = dl.get("url")
                if dl_url:
                    stremio_streams.append({
                        "name": "StreamMafia",
                        "title": f"{quality} | {lang}",
                        "url": dl_url
                    })
                    
        return stremio_streams
    except Exception as e:
        print(f"Error fetching streams: {e}")
        return []

# Stremio Addon Manifest
@app.route('/manifest.json')
def addon_manifest():
    return jsonify({
        "id": "org.streammafia.addon",
        "version": "1.0.0",
        "name": "StreamMafia",
        "description": "Stream movies and series from StreamMafia",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "catalogs": [],
        "idPrefixes": ["tt"]
    })

# Standard Stremio Stream Route
@app.route('/stream/<type>/<id>.json')
def addon_stream(type, id):
    streams = get_streams(id)
    return jsonify({"streams": streams})

# User Requested Route: /movie?imdbid={{id}}
@app.route('/movie')
def get_movie_by_imdb():
    imdb_id = request.args.get('imdbid')
    if not imdb_id:
        return jsonify({"error": "Missing imdbid parameter"}), 400
        
    streams = get_streams(imdb_id)
    return jsonify({"streams": streams})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8002, debug=True)
