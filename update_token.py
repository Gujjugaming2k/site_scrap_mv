import os
import re
import base64
import requests

# Token files
netflix_token_file = "netflix_cookie.txt"
prime_token_file = "prime_cookie.txt"

def read_token(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            token = f.read().strip()
            return token.replace("in=", "")
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return ""

netflix_token = read_token(prime_token_file)
prime_token = read_token(prime_token_file)

# Regex patterns
pattern_token = re.compile(r"in=[^&]+")
pattern_stream_proxy = re.compile(r"https://iosmirror\.vflix\.life/api/stream-proxy\?[^ \n]+")
referer_string = "&referer=https%3A%2F%2Fnet51.cc"

# Base64 credentials
ENCODED_TOKEN = "MTExODY0NTYyNDpBQUZzNHBBd3NMRG9vOTVjWDZwUGU5cEQxb0w1QjFoaTlzNA=="
ENCODED_CHANNEL_ID = "LTEwMDIxOTY1MDM3MDU="
BOT_TOKEN = base64.b64decode(ENCODED_TOKEN).decode("utf-8")
CHANNEL_ID = base64.b64decode(ENCODED_CHANNEL_ID).decode("utf-8")

# Folder definitions
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

# Track updates
update_counts = {}

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

# Run processing
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
    lines.append("")  # Blank line between platforms

telegram_message = "\n".join(lines).strip()

# Send Telegram message
response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    data={
        "chat_id": CHANNEL_ID,
        "text": telegram_message,
        "parse_mode": "Markdown"
    }
)

if response.status_code == 200:
    print("📨 Telegram message sent successfully.")
else:
    print(f"❌ Telegram error: {response.text}")
