from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import re

app = Flask(__name__)
CORS(app)

TMDB_API_KEY = "ea7b1fc3807d8a53d4227a80a15aeed1"
BASE_URL = "https://hdghartv.cc/api"

MANIFEST = {
    "id": "org.hdghartv.addon",
    "version": "1.0.0",
    "name": "HDGharTV",
    "description": "Streaming data from HDGharTV",
    "resources": ["catalog", "stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"],
    "catalogs": [
        {
            "type": "movie",
            "id": "hdghartv_movies",
            "name": "HDGharTV Movies",
            "extra": [{"name": "search", "isRequired": False}]
        },
        {
            "type": "series",
            "id": "hdghartv_series",
            "name": "HDGharTV Series",
            "extra": [{"name": "search", "isRequired": False}]
        }
    ]
}

# Simple cache for TMDB resolution
imdb_to_tmdb_cache = {}

session = requests.Session()

def get_tmdb_info(imdb_id):
    if imdb_id in imdb_to_tmdb_cache:
        return imdb_to_tmdb_cache[imdb_id]
    
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    try:
        response = session.get(url, timeout=5)
        data = response.json()
        
        result = None
        if data.get("movie_results"):
            res = data["movie_results"][0]
            result = {"tmdb_id": res["id"], "title": res["title"], "type": "movie"}
        elif data.get("tv_results"):
            res = data["tv_results"][0]
            result = {"tmdb_id": res["id"], "title": res["name"], "type": "series"}
            
        if result:
            imdb_to_tmdb_cache[imdb_id] = result
        return result
    except Exception as e:
        print(f"TMDB Error for {imdb_id}: {e}")
        return None

def search_hdghartv(query):
    url = f"{BASE_URL}/search/suggestions?q={query}"
    try:
        response = session.get(url, timeout=5)
        return response.json()
    except Exception as e:
        print(f"Search Error for {query}: {e}")
        return []

def get_details(item_id, item_type):
    endpoint = "movies" if item_type == "movie" else "series"
    url = f"{BASE_URL}/{endpoint}/public/{item_id}"
    try:
        response = session.get(url, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Detail Error for {item_id}: {e}")
        return None

@app.route("/")
def index():
    return "HDGharTV Stremio Addon is running."

@app.route("/manifest.json")
def manifest():
    return jsonify(MANIFEST)

@app.route("/catalog/<type>/<id>.json")
@app.route("/catalog/<type>/<id>/search=<query>.json")
def catalog(type, id, query=None):
    if not query:
        return jsonify({"metas": []})
    
    results = search_hdghartv(query)
    metas = []
    for item in results:
        if item.get("type") not in ["movie", "series"]:
            continue
            
        metas.append({
            "id": f"tt_hdg_{item['id']}", 
            "type": item["type"],
            "name": item["title"],
            "poster": item.get("image"),
            "releaseInfo": item.get("year"),
        })
    
    return jsonify({"metas": metas})

@app.route("/stream/<type>/<id>.json")
def stream(type, id):
    streams = []
    print(f"Stream request for {type} {id}")
    
    # Extract ID info
    if ":" in id:
        parts = id.split(":")
        imdb_id = parts[0]
        season = parts[1]
        episode = parts[2]
    else:
        imdb_id = id
        season = None
        episode = None
        
    if not imdb_id.startswith("tt"):
        # Not an IMDb ID, maybe one of ours?
        # But Stremio usually sends IMDb for playback.
        return jsonify({"streams": []})

    info = get_tmdb_info(imdb_id)
    if not info:
        print(f"Could not resolve TMDB info for {imdb_id}")
        return jsonify({"streams": []})
    
    tmdb_id = info["tmdb_id"]
    title = info["title"]
    print(f"Resolved {imdb_id} to TMDB:{tmdb_id} '{title}'")
    
    # Search for the title on HDGharTV
    results = search_hdghartv(title)
    
    for item in results:
        if item.get("type") != info["type"]:
            continue
        
        # Small optimization: Check if name matches roughly (can be refined)
        # For now, let's just fetch details as requested
        
        details = get_details(item["id"], item["type"])
        if not details:
            continue
        
        if details.get("tmdbId") == tmdb_id:
            print(f"Found match on HDGharTV: {item['id']}")
            if info["type"] == "movie":
                links = details.get("streamingLinks", [])
                for link in links:
                    if link.get("isActive"):
                        streams.append({
                            "name": f"HDGharTV\n{link['quality']}",
                            "title": f"{details.get('title')}\n{link['quality']}",
                            "url": link["url"],
                            "behaviorHints": {"notWebReady": True if link.get("type") == "hls" else False}
                        })
                break
            
            elif info["type"] == "series" and season and episode:
                found_ep = None
                for s in details.get("seasons", []):
                    if str(s.get("seasonNumber")) == str(season):
                        for ep in s.get("episodes", []):
                            if str(ep.get("episodeNumber")) == str(episode):
                                found_ep = ep
                                break
                    if found_ep: break
                
                if found_ep:
                    links = found_ep.get("streamingLinks", [])
                    for link in links:
                        if link.get("isActive"):
                            streams.append({
                                "name": f"HDGharTV\n{link['quality']}",
                                "title": f"S{season} E{episode} - {found_ep.get('name')}\n{link['quality']}",
                                "url": link["url"],
                                "behaviorHints": {"notWebReady": True if link.get("type") == "hls" else False}
                            })
                break

    return jsonify({"streams": streams})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004, debug=True)
