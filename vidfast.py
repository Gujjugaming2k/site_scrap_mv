from flask import Flask, request, jsonify
import re
import base64
import requests
from Crypto.Cipher import AES
from urllib.parse import urlparse
from Crypto.Util.Padding import pad

app = Flask(__name__)

# Custom Base64 encoder with character mapping
def custom_encode(input_bytes):
    source_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    target_chars = "OCmbtfWoski0dEv3HFhu_G1cDUw6QARY87-VJpjqlNLTIZrX249PeSnBgz5MaxyK"
    translation_table = str.maketrans(source_chars, target_chars)
    encoded = base64.urlsafe_b64encode(input_bytes).decode().rstrip('=')
    return encoded.translate(translation_table)

# AES encryption setup
key_hex = '5b783a7f09f7e006661a5ebf3ef8952fdfc03e41892bf1597f7d8dda49dcb6a9'
iv_hex = 'a3d48b44795d9c2592ee4c3294258242'
aes_key = bytes.fromhex(key_hex)
aes_iv = bytes.fromhex(iv_hex)

# XOR key
xor_key = bytes.fromhex("11860f0e9ebe20c03c")

# Static path used in API URLs
static_path = "1000090675158710"

# Target server names to filter
target_names = ['Alpha']

@app.route('/get_video', methods=['GET'])
def get_video():
    tmdb_id = request.args.get('id')
    if not tmdb_id:
        return jsonify({"error": "Missing TMDB ID"}), 400

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

    try:
        response = requests.get(base_url, headers=headers).text
        match = re.search(r'\\"en\\":\\"(.*?)\\"', response)
        if not match:
            return jsonify({"error": "No data found"}), 404

        raw_data = match.group(1)
        cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
        padded_data = pad(raw_data.encode(), AES.block_size)
        aes_encrypted = cipher.encrypt(padded_data)

        xor_result = bytes(b ^ xor_key[i % len(xor_key)] for i, b in enumerate(aes_encrypted))
        encoded_final = custom_encode(xor_result)

        api_servers = f"https://vidfast.pro/{static_path}/DJIvtQ/{encoded_final}"
        server_response = requests.post(api_servers, headers=headers, json={}).json()

        results = []
        for entry in server_response:
            if entry.get('name') in target_names:
                name = entry.get('name')
                data_token = entry.get('data')
                api_stream = f"https://vidfast.pro/{static_path}/cz7wg6oT0Q/{data_token}"
                try:
                    video_response = requests.post(api_stream, headers=headers).json()
                    video_url = video_response.get('url', 'No URL found')
                except Exception as e:
                    video_url = f"Error fetching URL: {e}"

                results.append({
                    "Name": name,
                    "Video URL": video_url,
                    "Referer Header": default_domain
                })

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True,port=5019)
