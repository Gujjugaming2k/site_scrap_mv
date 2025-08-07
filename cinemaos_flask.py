from flask import Flask, jsonify
import requests
import json
from urllib.parse import urlparse
from Crypto.Cipher import AES
from flask import redirect, abort

app = Flask(__name__)

# Constants
user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
key_hex = "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456"
key = bytes.fromhex(key_hex)

def decrypt_data(encrypted_hex, iv_hex, auth_tag_hex):
    ciphertext = bytes.fromhex(encrypted_hex)
    iv = bytes.fromhex(iv_hex)
    auth_tag = bytes.fromhex(auth_tag_hex)

    cipher = AES.new(key, AES.MODE_GCM, nonce=iv)
    cipher.update(b'')  # AAD
    decrypted = cipher.decrypt(ciphertext).decode('utf-8')
    cipher.verify(auth_tag)
    return decrypted

def fetch_stream_url(tmdb_id, language):
    base_url = f"https://cinemaos.live/movie/watch/{tmdb_id}"
    parsed_url = urlparse(base_url)
    default_domain = f"{parsed_url.scheme}://{parsed_url.netloc}/"

    headers = {
        "Accept": "*/*",
        "Referer": default_domain,
        "User-Agent": user_agent,
    }

    # Auth token
    auth_api = f'{default_domain}/api/auth'
    auth_response = requests.get(auth_api, headers=headers).json()
    auth_token = requests.post(auth_api, headers=headers, json=auth_response).json()['token']
    headers['Authorization'] = f'Bearer {auth_token}'

    # Movie metadata
    data_response = requests.get(f"{default_domain}/api/downloadLinks?type=movie&tmdbId={tmdb_id}").json()['data'][0]
    release_year = data_response['releaseYear']
    title = data_response['movieTitle']
    imdb_id = data_response['subtitleLink'].split('=')[-1]

    # Encrypted stream data
    enc_response = requests.get(
        f"{default_domain}/api/cinemaos?type=movie&tmdbId={tmdb_id}&imdbId={imdb_id}&t={title}&ry={release_year}",
        headers=headers
    ).json()['data']

    decrypted_data = decrypt_data(enc_response['encrypted'], enc_response['cin'], enc_response['mao'])
    sources = json.loads(decrypted_data).get('sources', {})

    return {
        "url": sources.get(language, {}).get("url"),
        "title": title,
        "release_year": release_year,
        "imdb_id": imdb_id
    }
@app.route('/fetch_hindi/<tmdb_id>')
def fetch_hindi(tmdb_id):
    result = fetch_stream_url(tmdb_id, "Hindi")
    url = result.get("url") if isinstance(result, dict) else result
    if url:
        return redirect(url)
    else:
        return abort(404, description="Hindi stream not found")

@app.route('/fetch_english/<tmdb_id>')
def fetch_english(tmdb_id):
    result = fetch_stream_url(tmdb_id, "English")
    url = result.get("url") if isinstance(result, dict) else result
    if url:
        return redirect(url)
    else:
        return abort(404, description="English stream not found")


@app.route('/fetch_all/<tmdb_id>')
def fetch_all(tmdb_id):
    hindi_data = fetch_stream_url(tmdb_id, "Hindi")
    english_data = fetch_stream_url(tmdb_id, "English")

    return jsonify({
        "title": hindi_data["title"],
        "release_year": hindi_data["release_year"],
        "imdb_id": hindi_data["imdb_id"],
        "Hindi_URL": hindi_data["url"] or "Not found",
        "English_URL": english_data["url"] or "Not found"
    })


if __name__ == '__main__':
    app.run(debug=True, port=5019)
