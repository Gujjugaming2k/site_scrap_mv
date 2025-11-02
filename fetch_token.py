import os
import re
import json
import base64
import requests

# Base64-encoded credentials
ENCODED_TOKEN = "MTExODY0NTYyNDpBQUZzNHBBd3NMRG9vOTVjWDZwUGU5cEQxb0w1QjFoaTlzNA=="
ENCODED_CHANNEL_ID = "LTEwMDIxOTY1MDM3MDU="

# Decode credentials
BOT_TOKEN = base64.b64decode(ENCODED_TOKEN).decode("utf-8")
CHANNEL_ID = base64.b64decode(ENCODED_CHANNEL_ID).decode("utf-8")

# Regex patterns
pattern_token = re.compile(r"in=[^&]+")
pattern_stream_proxy = re.compile(r"https://iosmirror\.vflix\.life/api/stream-proxy\?[^ \n]+")
referer_string = "&referer=https%3A%2F%2Fnet51.cc"

def get_prime_cookie():
    url = "https://net51.cc/tv/p.php"
    response = requests.get(url)
    set_cookie = response.headers.get("Set-Cookie")
    if set_cookie:
        match = re.search(r't_hash=([^;]+)', set_cookie)
        if match:
            return match.group(1)
    return None

def handle_netflix(cookie_value):
    url = "https://net20.cc/play.php"
    payload = {"id": "81705721"}
    headers = {"Cookie": f"t_hash_t={cookie_value}"}
    response = requests.post(url, data=payload, headers=headers)
    try:
        data = response.json()
        h_value = data.get("h", "")
        if h_value.startswith("in="):
            print("✅ Netflix token fetched.")
            return h_value.replace("in=", "")
    except json.JSONDecodeError:
        print("❌ Failed to parse Netflix JSON response.")
    return ""

def handle_prime(prime_cookie):
    url = "https://net51.cc/pv/playlist.php?id=0IOXQJ1CQWMH3Y1FNVUO30OSME&tm=1761932966"
    headers = {"Cookie": f"t_hash_t={prime_cookie}"}
    response = requests.post(url, headers=headers)
    try:
        data = response.json()
        seen = set()
        for item in data:
            for source in item.get("sources", []):
                file_url = source.get("file", "")
                match = re.search(r'in=([a-f0-9]{32}::[a-f0-9]{32}::\d+::[a-z]+)', file_url)
                if match:
                    in_value = match.group(1)
                    if in_value not in seen:
                        seen.add(in_value)
                        print("✅ Prime token fetched.")
                        return in_value
    except json.JSONDecodeError:
        print("❌ Failed to parse Prime JSON response.")
    return ""

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        print("📨 Telegram message sent.")
    else:
        print("❌ Telegram error:", response.text)

def process_file(src_path, dst_path, token):
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "in=" in content:
            content = pattern_token.sub(f"in={token}", content)
        else:
            print(f"⚠️ No token found in: {src_path}")

        def ensure_referer(match):
            url = match.group(0)
            return url if "&referer=" in url else url + referer_string

        content = pattern_stream_proxy.sub(ensure_referer, content)

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"❌ Error processing {src_path}: {e}")
        return False

def walk_and_process(src_root, dst_root, token):
    count = 0
    for root, _, files in os.walk(src_root):
        for file in files:
            if file.endswith(".strm"):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, src_root)
                dst_path = os.path.join(dst_root, rel_path)
                if process_file(src_path, dst_path, token):
                    count += 1
    return count

def count_series_folders(series_root):
    if not os.path.isdir(series_root):
        return 0
    return len([
        folder for folder in os.listdir(series_root)
        if os.path.isdir(os.path.join(series_root, folder))
    ])

# === Main Execution ===

cookie = get_prime_cookie()
prime_cookie = get_prime_cookie()

if cookie and prime_cookie:
    netflix_token = handle_netflix(cookie)
    prime_token = handle_prime(prime_cookie)

    if netflix_token and prime_token:
        message = f"*IOSMIRROR Token:*\n`in={prime_token}`"
        send_to_telegram(message)

        platforms = {
            "Netflix": {
                "token": netflix_token,
                "folders": {
                    "Movies": ("Netflix/Movies", "Netflix/Movies"),
                    "Series": ("Netflix/Series", "Netflix/Series")
                }
            },
            "Prime": {
                "token": prime_token,
                "folders": {
                    "Movies": ("Prime/Movies", "Prime/Movies"),
                    "Series": ("Prime/Series", "Prime/Series")
                }
            },
            "Hotstar": {
                "token": prime_token,
                "folders": {
                    "Movies": ("Hotstar/Movies", "Hotstar/Movies"),
                    "Series": ("Hotstar/Series", "Hotstar/Series")
                }
            }
        }

        update_counts = {}
        for platform, config in platforms.items():
            update_counts[platform] = {}
            for label, (src, dst) in config["folders"].items():
                updated = walk_and_process(src, dst, config["token"])
                update_counts[platform][label] = updated

                if label == "Series":
                    series_count = count_series_folders(src)
                    update_counts[platform]["Total Series"] = series_count

                print(f"✅ {platform} {label} updated - {updated} files")

        # Build Telegram message
        lines = []
        for platform, sections in update_counts.items():
            lines.append(f"{platform}")
            for label, count in sections.items():
                lines.append(f"- {label} updated: {count}")
            lines.append("")

        telegram_message = "\n".join(lines).strip()
        send_to_telegram(telegram_message)

    else:
        print("❌ Missing one or both tokens. Skipping update.")
else:
    print("❌ Failed to retrieve one or both cookies.")
