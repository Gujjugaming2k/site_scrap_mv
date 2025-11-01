import os
import re
import base64
import requests

# Token files
netflix_token_file = "netflix_cookie.txt"
prime_token_file = "prime_cookie.txt"

# Read token from file and strip accidental 'in=' prefix
def read_token(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            token = f.read().strip()
            return token.replace("in=", "")
    except Exception as e:
        print(f"❌ Error reading {path}: {e}")
        return ""

# Load tokens
netflix_token = read_token(prime_token_file)
prime_token = read_token(prime_token_file)

# Source and destination folders
sources = {
    "Netflix": os.path.join("Netflix", "Movies"),
    "Prime": os.path.join("Prime", "Movies"),
    "Hotstar": os.path.join("Hotstar", "Movies")
}
destinations = {
    "Netflix": os.path.join("Netflix", "Movies"),
    "Prime": os.path.join("Prime", "Movies"),
    "Hotstar": os.path.join("Hotstar", "Movies")
}

# Regex to replace token after in=
pattern_token = re.compile(r"in=[^&]+")

# Regex to find full stream-proxy URLs
pattern_stream_proxy = re.compile(
    r"https://iosmirror\.vflix\.life/api/stream-proxy\?[^ \n]+"
)

# Referer string to append if missing
referer_string = "&referer=https%3A%2F%2Fnet51.cc"

# Track update counts
update_counts = {
    "Netflix": 0,
    "Prime": 0,
    "Hotstar": 0
}

# Process each platform
for platform in sources:
    src_dir = sources[platform]
    dst_dir = destinations[platform]
    os.makedirs(dst_dir, exist_ok=True)

    for filename in os.listdir(src_dir):
        src_path = os.path.join(src_dir, filename)
        dst_path = os.path.join(dst_dir, filename)

        if os.path.isfile(src_path):
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Choose token
            token = netflix_token if platform == "Netflix" else prime_token

            # Replace token
            new_content = pattern_token.sub(f"in={token}", content)

            # Ensure referer is present
            def ensure_referer(match):
                url = match.group(0)
                return url if "&referer=" in url else url + referer_string

            new_content = pattern_stream_proxy.sub(ensure_referer, new_content)

            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            update_counts[platform] += 1

    print(f"✅ {platform} files processed and saved to '{dst_dir}'")

# Prepare Telegram message
message_lines = [f"{platform} updated - {count}" for platform, count in update_counts.items()]
telegram_message = "\n".join(message_lines)

# Base64-encoded credentials
ENCODED_TOKEN = "MTExODY0NTYyNDpBQUZzNHBBd3NMRG9vOTVjWDZwUGU5cEQxb0w1QjFoaTlzNA=="
ENCODED_CHANNEL_ID = "LTEwMDIxOTY1MDM3MDU="

# Decode credentials
BOT_TOKEN = base64.b64decode(ENCODED_TOKEN).decode("utf-8")
CHANNEL_ID = base64.b64decode(ENCODED_CHANNEL_ID).decode("utf-8")

# Send message to Telegram
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
    print(f"❌ Failed to send Telegram message: {response.text}")
