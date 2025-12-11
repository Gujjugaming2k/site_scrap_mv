from flask import Flask, jsonify, request
import re
import base64
import requests
from Crypto.Cipher import AES
from urllib.parse import urlparse
from Crypto.Util.Padding import unpad

app = Flask(__name__)

USER_AGENT = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
KEY_HEX = "6966796f75736372617065796f75617265676179000000000000000000000000"


def decrypt_vidzee(encrypted_url):
    decoded = base64.b64decode(encrypted_url).decode()
    iv_b64, ciphertext_b64 = decoded.split(":", 1)

    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(ciphertext_b64)
    key = bytes.fromhex(KEY_HEX)

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    plaintext = unpad(decrypted, AES.block_size)

    return plaintext.decode("utf-8")


def fetch_server(base_url, server_number):
    default_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(base_url))

    headers = {
        "Referer": default_domain,
        "User-Agent": USER_AGENT
    }

    media_type = "movie" if "movie" in base_url else "tv"

    match = re.search(r"/(\d+)(?:/(\d+)/(\d+))?", base_url)
    media_id = match.group(1)

    if media_type == "tv":
        season = match.group(2)
        episode = match.group(3)
        api_url = (
            f"https://player.vidzee.wtf/api/server?"
            f"id={media_id}&sr={server_number}&ss={season}&ep={episode}"
        )
    else:
        api_url = f"https://player.vidzee.wtf/api/server?id={media_id}&sr={server_number}"

    response = requests.get(api_url, headers=headers).json()

    if not response.get("url"):
        return None

    encrypted_url = response["url"][0]["link"]
    video_url = decrypt_vidzee(encrypted_url)

    return video_url


def process_vidzee(base_url):
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
            name = f"English - Vidzee Server {server}"
            title = "English - HLS Stream"
        else:
            name = f"Vidzee Server {server}"
            title = "HLS Stream"

        stream_obj = {
            "url": video_url,
            "name": name,
            "title": title,
            "behaviorHints": {
                "bingeGroup": "VFlixPrime-vidzee-streams"
            }
        }

        streams.append(stream_obj)

    return jsonify({"streams": streams})


# ✅ Movie route
@app.route("/movie/<int:media_id>.json")
def movie_route(media_id):
    base_url = f"https://player.vidzee.wtf/embed/movie/{media_id}"
    return process_vidzee(base_url)


# ✅ Series route
@app.route("/series/<path:data>.json")
def series_route(data):
    try:
        media_id, season, episode = data.split(":")
    except ValueError:
        return jsonify({"error": "Invalid format. Use /series/id:season:episode.json"}), 400

    base_url = f"https://player.vidzee.wtf/embed/tv/{media_id}/{season}/{episode}"
    return process_vidzee(base_url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
