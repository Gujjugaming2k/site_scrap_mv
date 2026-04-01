import re
import urllib.parse
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for Stremio addon compatibility
CORS(app)

TMDB_API_KEY = "ea7b1fc3807d8a53d4227a80a15aeed1"

PROVIDERS = {
    "netflix": "netflix",
    "jio": "hotstar",
    "prime": "prime"
}

def get_title_from_tmdb(imdb_id):
    """Fetch movie or TV show title from TMDB using IMDb ID."""
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    try:
        resp = requests.get(url).json()
        if "movie_results" in resp and resp["movie_results"]:
            return resp["movie_results"][0].get("title")
        elif "tv_results" in resp and resp["tv_results"]:
            return resp["tv_results"][0].get("name")
    except Exception as e:
        print(f"Error fetching TMDB data: {e}")
    return None

def clean_title(title):
    """Remove special characters and keep alphanumeric spaces."""
    return re.sub(r'[^a-zA-Z0-9 ]', '', title).strip()

def fetch_cinefy_streams(title, season=None, episode=None):
    """Searches Cinefy APIs for the given title and returns HLS stream links."""
    cleaned_title = clean_title(title)
    encoded_query = urllib.parse.quote(cleaned_title)
    
    streams = []
    
    for provider_name, provider_path in PROVIDERS.items():
        search_url = f"https://cinefy.lol/api/{provider_path}/search?q={encoded_query}"
        try:
            search_resp = requests.get(search_url).json()
            if search_resp.get("success") and search_resp.get("data"):
                # Take the first matched item
                item = search_resp["data"][0]
                item_id = item["id"]
                item_title = item.get("title", cleaned_title)
                target_id = item_id
                episode_title = None
                
                if season is not None and episode is not None:
                    # It's a series, fetch the load info to get seasons
                    load_url = f"https://cinefy.lol/api/{provider_path}/load/{item_id}"
                    load_resp = requests.get(load_url).json()
                    
                    if load_resp.get("success") and "data" in load_resp:
                        seasons = load_resp["data"].get("seasons", [])
                        season_id = next((s.get("id") for s in seasons if s.get("label") == str(season)), None)
                        
                        if not season_id:
                            continue # Season not found
                            
                        # Fetch episodes for this season
                        episodes_url = f"https://cinefy.lol/api/{provider_path}/episodes/{item_id}/{season_id}"
                        episodes_resp = requests.get(episodes_url).json()
                        
                        if episodes_resp.get("success") and "data" in episodes_resp:
                            eps = episodes_resp["data"]
                            ep_obj = next((ep for ep in eps if ep.get("episode") == str(episode)), None)
                            
                            if not ep_obj or not ep_obj.get("id"):
                                continue # Episode not found
                                
                            target_id = ep_obj["id"]
                            episode_title = ep_obj.get("title")
                        else:
                            continue # Failed to get episodes
                    else:
                        continue # Failed to load series data
                
                encoded_item_title = urllib.parse.quote(item_title)
                links_url = f"https://cinefy.lol/api/{provider_path}/links/{target_id}?title={encoded_item_title}"
                
                display_title = item_title
                if episode_title:
                    display_title = f"{item_title} - {episode_title}"
                
                links_resp = requests.get(links_url).json()
                if links_resp.get("success") and links_resp.get("sources"):
                    for source in links_resp["sources"]:
                        if source.get("type") == "hls":
                            file_url = source.get("file")
                            # If the URL is a relative proxy path, prepend the base domain
                            if file_url and file_url.startswith("/"):
                                file_url = f"https://cinefy.lol{file_url}"
                                
                            streams.append({
                                "provider": provider_name,
                                "movie_title": display_title,
                                "label": source.get("label", "Unknown"),
                                "url": file_url,
                                "type": "hls"
                            })
        except Exception as e:
            print(f"Error fetching from {provider_name}: {e}")
            continue
            
    return streams

# ----------------- STREMIO ADDON ROUTES -----------------

@app.route('/manifest.json')
def addon_manifest():
    return jsonify({
        "id": "org.cinefy.stremio",
        "version": "1.0.0",
        "name": "Cinefy Streams",
        "description": "Fetches streams from Cinefy (Netflix, Prime, Jio)",
        "types": ["movie", "series"],
        "catalogs": [],
        "resources": ["stream"]
    })

@app.route('/stream/<string:type>/<string:id_json>')
def addon_stream(type, id_json):
    """Stremio endpoint: e.g., /stream/movie/tt1234567.json or /stream/series/tt1234567:1:1.json"""
    # Extract IMDb ID and drop the .json extension
    full_id = id_json.replace('.json', '')
    
    parts = full_id.split(':')
    base_imdb_id = parts[0]
    season = parts[1] if len(parts) > 1 else None
    episode = parts[2] if len(parts) > 2 else None
    
    title = get_title_from_tmdb(base_imdb_id)
    if not title:
        return jsonify({"streams": []})
        
    cinefy_streams = fetch_cinefy_streams(title, season, episode)
    
    # Convert format to Stremio Stream Object
    stremio_streams = []
    for stream in cinefy_streams:
        stremio_streams.append({
            "name": f"Cinefy {stream['provider'].capitalize()}",
            "title": f"{stream['movie_title']}\n{stream['label']}",
            "url": stream['url']
        })
        
    return jsonify({"streams": stremio_streams})

# ----------------- GENERIC API ROUTE -----------------

@app.route('/api/search/<string:full_id>')
def generic_search(full_id):
    """Generic endpoint: /api/search/tt1234567 or /api/search/tt1234567:1:1"""
    parts = full_id.split(':')
    base_imdb_id = parts[0]
    season = parts[1] if len(parts) > 1 else None
    episode = parts[2] if len(parts) > 2 else None

    title = get_title_from_tmdb(base_imdb_id)
    if not title:
        return jsonify({"error": "Title not found for given IMDb ID"}), 404
        
    streams = fetch_cinefy_streams(title, season, episode)
    return jsonify({
        "success": True, 
        "title_found": title,
        "streams": streams
    })


if __name__ == '__main__':
    # Running on port 5000
    app.run(host='0.0.0.0', port=8003, debug=True)
