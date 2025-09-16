from flask import Flask, request, jsonify
import re
import base64
import requests
from Crypto.Cipher import AES
from urllib.parse import urlparse
from Crypto.Util.Padding import pad
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)




# Custom Base64 encoder with character mapping
def custom_encode(input_bytes):
    source_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    target_chars = "SCHkQ7-ni29AJs3VKw4XxjZE5WNL6zTBbY0G1ReurtmDMyqgIl8cvoOUPfFdhap_"
    translation_table = str.maketrans(source_chars, target_chars)
    encoded = base64.urlsafe_b64encode(input_bytes).decode().rstrip('=')
    return encoded.translate(translation_table)

# AES encryption setup
key_hex = '8321a6aa7add8f2874b4b03f4f0fd9de8fa33bb91d9fa63534975ab49a584c8f'
iv_hex = '7d7a35a72b54d40c323d64d268e84382'
aes_key = bytes.fromhex(key_hex)
aes_iv = bytes.fromhex(iv_hex)

# XOR key
xor_key = bytes.fromhex("7ce1477edc99e718b8")

# Static path used in API URLs
static_path = "hezushon/e7b3cf8497ae580e7a703f996cf17ce48587cbd5/ev/9fdf613a9204683a789e4bfe9fd06da405e6ef36c4338b5baf14d0f2ea18f7a4"

# Target server names to filter
target_names = ['Alpha']
def fetch_stream_data(tmdb_id):
    base_url = f"https://vidfast.pro/movie/{tmdb_id}"
    default_domain = '{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(base_url))
    headers = {
        "Accept": "*/*",
        "Referer": default_domain,
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
        "x-session": "",
        "Content-Type": "application/x-shockwave-flash",
        "X-Requested-With": "XMLHttpRequest",
    }

    response = requests.get(base_url, headers=headers).text
    soup = BeautifulSoup(response, 'html.parser')
    title_tag = soup.find('div', class_='MuiBox-root mui-10rvbm3')
    movie_title = title_tag.text.strip() if title_tag else "Unknown Title"

    match = re.search(r'\\"en\\":\\"(.*?)\\"', response)
    if not match:
        return None, "No data found"

    raw_data = match.group(1)
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
    padded_data = pad(raw_data.encode(), AES.block_size)
    aes_encrypted = cipher.encrypt(padded_data)

    xor_result = bytes(b ^ xor_key[i % len(xor_key)] for i, b in enumerate(aes_encrypted))
    encoded_final = custom_encode(xor_result)

    api_servers = f"https://vidfast.pro/{static_path}/DJIvtQ/{encoded_final}"
    server_response = requests.post(api_servers, headers=headers, json={}).json()

    for entry in server_response:
        if entry.get('name') in target_names:
            name = entry.get('name')
            data_token = entry.get('data')
            api_stream = f"https://vidfast.pro/{static_path}/cz7wg6oT0Q/{data_token}"
            video_response = requests.post(api_stream, headers=headers).json()
            video_url = video_response.get('url', 'No URL found')

            encoded_video_url = urllib.parse.quote(video_url, safe='')
            headers_json = '{"referer":"' + default_domain + '"}'
            encoded_headers = urllib.parse.quote(headers_json, safe='')

            proxy_url = f"https://proxy.vflix.life/m3u8-proxy?url={encoded_video_url}&headers={encoded_headers}"

            return {
                "Name": name,
                "Title": movie_title,
                "Video URL": video_url,
                "Strem URL": proxy_url,
                "Referer Header": default_domain
            }, None

    return None, "No matching stream found"

@app.route('/get_video', methods=['GET'])
def get_video():
    tmdb_id = request.args.get('id')
    if not tmdb_id:
        return jsonify({"error": "Missing TMDB ID"}), 400

    try:
        result, error = fetch_stream_data(tmdb_id)
        if error:
            return jsonify({"error": error}), 404
        return jsonify([result])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from flask import redirect  # Make sure this is imported

@app.route('/redirect', methods=['GET'])
def redirect_to_stream():
    tmdb_id = request.args.get('id')
    if not tmdb_id:
        return jsonify({"error": "Missing TMDB ID"}), 400

    try:
        result, error = fetch_stream_data(tmdb_id)
        if error:
            return jsonify({"error": error}), 404
        return redirect(result["Strem URL"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True,port=5019)
