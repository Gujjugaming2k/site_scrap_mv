from flask import Flask, jsonify
import re
import base64
import requests
from Crypto.Cipher import AES
from urllib.parse import urlparse
from Crypto.Util.Padding import unpad

app = Flask(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

# Vidzee AES key
KEY_HEX = "6966796f75736372617065796f75617265676179000000000000000000000000"

# ✅ 3 TMDB API keys (rotate on failure)
TMDB_KEYS = [
    "e3c47f86a8cecb8721f9cc45a1e1ba8f",
    "ea7b1fc3807d8a53d4227a80a15aeed1",
    "abf4d0f9cf2c7ad4990823215af63543",
    "83aa53347a84d73e55c6ada9e5d537fe"
]


# ---------------------------------------------------------
# ✅ AES Decryption for Vidzee
# ---------------------------------------------------------
def decrypt_vidzee(encrypted_url: str) -> str:
    decoded = base64.b64decode(encrypted_url).decode()
    iv_b64, ciphertext_b64 = decoded.split(":", 1)

    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    key = bytes.fromhex(KEY_HEX)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    plaintext = unpad(decrypted, AES.block_size)

    return plaintext.decode("utf-8")


# ---------------------------------------------------------
# ✅ TMDB Request with 3-key retry
# ---------------------------------------------------------
def tmdb_request(url):
    for key in TMDB_KEYS:
        try:
            full_url = f"{url}&api_key={key}"
            r = requests.get(full_url, timeout=5)

            if r.status_code == 200:
                return r.json()

            if r.status_code == 429:  # rate limit
                continue

        except Exception:
            continue

    return None  # all keys failed


# ---------------------------------------------------------
# ✅ IMDB → TMDB (Movie)
# ---------------------------------------------------------
def imdb_to_tmdb_movie(imdb_id: str):
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id"
    data = tmdb_request(url)

    if not data:
        return None

    results = data.get("movie_results") or []
    return results[0]["id"] if results else None


# ---------------------------------------------------------
# ✅ IMDB → TMDB (TV)
# ---------------------------------------------------------
def imdb_to_tmdb_tv(imdb_id: str):
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?external_source=imdb_id"
    data = tmdb_request(url)

    if not data:
        return None

    results = data.get("tv_results") or []
    return results[0]["id"] if results else None


# ---------------------------------------------------------
# ✅ Fetch Vidzee Server
# ---------------------------------------------------------
def fetch_server(base_url: str, server_number: int):
    default_domain = "{uri.scheme}://{uri.netloc}/".format(uri=urlparse(base_url))

    headers = {
        "Referer": default_domain,
        "User-Agent": USER_AGENT,
    }

    media_type = "movie" if "movie" in base_url else "tv"

    match = re.search(r"/(\d+)(?:/(\d+)/(\d+))?", base_url)
    if not match:
        return None

    media_id = match.group(1)

    if media_type == "tv":
        season = match.group(2)
        episode = match.group(3)
        api_url = (
            "https://player.vidzee.wtf/api/server"
            f"?id={media_id}&sr={server_number}&ss={season}&ep={episode}"
        )
    else:
        api_url = (
            "https://player.vidzee.wtf/api/server"
            f"?id={media_id}&sr={server_number}"
        )

    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        data = resp.json()
    except Exception:
        return None

    if not data.get("url"):
        return None

    encrypted_url = data["url"][0]["link"]
    return decrypt_vidzee(encrypted_url)


# ---------------------------------------------------------
# ✅ Build Streams
# ---------------------------------------------------------
def process_vidzee(base_url: str):
    streams = []

    for server in [3, 6]:
        video_url = fetch_server(base_url, server)
        if not video_url:
            continue

        # ✅ Language rules
        if server == 6:
            name = f"Hindi - Vidzee {server}"
            title = "Hindi - HLS Stream"
        elif server == 3:
            name = f"Englis - Vidzee Server {server}"
            title = "Englis - HLS Stream"
        else:
            name = f"Vidzee Server {server}"
            title = "HLS Stream"

        streams.append({
            "url": video_url,
            "name": name,
            "title": title,
            "behaviorHints": {
                "bingeGroup": "VFlixPrime-vidzee-streams"
            }
        })

    return jsonify({"streams": streams})


# ---------------------------------------------------------
# ✅ Stremio Movie Route (IMDB ID)
# ---------------------------------------------------------
@app.route("/movie/<imdb_id>.json")
def movie_route(imdb_id):
    tmdb_id = imdb_to_tmdb_movie(imdb_id)
    if not tmdb_id:
        return jsonify({"streams": []})

    base_url = f"https://player.vidzee.wtf/embed/movie/{tmdb_id}"
    return process_vidzee(base_url)


# ---------------------------------------------------------
# ✅ Stremio Series Route (IMDB ID)
# ---------------------------------------------------------
@app.route("/series/<path:data>.json")
def series_route(data):
    try:
        imdb_id, season, episode = data.split(":")
    except ValueError:
        return jsonify({"error": "Invalid format. Use /series/imdb:season:episode.json"})

    tmdb_id = imdb_to_tmdb_tv(imdb_id)
    if not tmdb_id:
        return jsonify({"streams": []})

    base_url = f"https://player.vidzee.wtf/embed/tv/{tmdb_id}/{season}/{episode}"
    return process_vidzee(base_url)


# ---------------------------------------------------------
# ✅ Run Server
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
