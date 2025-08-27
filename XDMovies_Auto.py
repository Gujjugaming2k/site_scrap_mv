import os
import re
import json
import time
import requests
from urllib.parse import urlparse
import base64

# ---------- SETTINGS ----------
# Folder to save STRM files
STRM_FOLDER = "/tmp/opt/jellyfin/STRM/Provider/XDMovies/Movies"
# STRM file prefix
PREFIX = "https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url="

# Check interval (seconds)
CHECK_INTERVAL = 10 * 60   # 10 minutes
# Number of latest entries to monitor
CHECK_LIMIT = 99

# X Auth Token, Cloudflare clearance token and PHP session ID
x_auth_token = "njkddhdifdldjaslsjidoqdnasmnpo"  # static value from site, need to update if site changes it
cf_clearance = "ZxHtxMH6JLBeDBgnXF1znSoLDtM6usMwdHy2f35MnYo-1756267411-1.2.1.1-tgwhNPR8u2zNVVD2gfeEUtMm3t8uKpBysr7hMY.jyyCocKnNIx.bstkpU1HGaoVKAv98CtZlfQUDb4KlYvQj.sSSMKDiSHtxzGaX8dJDQllhDN9CyWUUh_EQKz2ZGqn5OjQikeELI8OUhF1.Z6yLYe2cNFFw2DwBSH1rJrrU5bIgYRUUNx12ucrlSGemsk7gbq8GQZExx1UkDQXLBkSnq8gRTjF3bLvBHK.n9doaWyA"
PHPSESSID = "k10svnq2ab74pgp7nr7uvqor2i"

# Headers (for both endpoints)
HEADERS_BASE = {
    "cookie": "PHPSESSID=" + PHPSESSID + "; cf_clearance=" + cf_clearance,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "x-auth-token": x_auth_token,   # This header is required
    "x-requested-with": "XMLHttpRequest" # This header is required
}

# API endpoints
API_URL = "https://xdmovies.site/php/fetch_media.php?sort=timestamp"
DETAILS_MOVIE = "https://xdmovies.site/api/xyz123?tmdb_id={}"



# Put your bot token & group chat id here

# Base64-encoded credentials
ENCODED_TOKEN = "NzUzMTYzNzg0NTpBQUYzR3hIbjFXYXBtX3gzeEsxYzlFOHBxbkFtZ3RCbGpBYw=="
ENCODED_CHANNEL_ID = "LTEwMDI4NzM0NTQ4MTk="

def decode_base64(encoded_str: str) -> str:
    """Decode a Base64-encoded string to UTF-8."""
    return base64.b64decode(encoded_str).decode('utf-8')

# Decode at runtime
TELEGRAM_BOT_TOKEN = decode_base64(ENCODED_TOKEN)
TELEGRAM_CHAT_ID = decode_base64(ENCODED_CHANNEL_ID)


# ---------- HELPERS ----------
def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def fetch_movie_details(tmdb_id):
    """Fetch detailed JSON for movie"""
    url = DETAILS_MOVIE.format(tmdb_id)
    headers = HEADERS_BASE.copy()
    headers["referer"] = f"https://xdmovies.site/details.html?id={tmdb_id}&type=movie"

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()

def send_telegram_message(text: str):
    """Send a message to Telegram group via Bot API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"   # allows bold, italic, etc. if you want
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except requests.RequestException as e:
        print(f"⚠️ Failed to send Telegram message: {e}")

def create_strm_files(movie_json):
    """Generate STRM files inside subfolder (only Hubcloud links allowed)"""
    title = movie_json.get("title", "Unknown")
    tmdb_id = movie_json.get("tmdb_id", "0")
    downloads = movie_json.get("download_links", [])

    # Filter only hubcloud links
    hubcloud_links = []
    for d in downloads:
        url = d.get("download_link", "")
        if url:
            domain = urlparse(url).netloc.lower()
            if "hubcloud." in domain:   # allows hubcloud.one, hubcloud.ink, etc.
                hubcloud_links.append(d)

    if not hubcloud_links:
        msg = f"⚠️ {title} [tmdbid-{tmdb_id}] - No Valid Hubcloud Links @tgH2R3"
        print(msg)
        send_telegram_message(msg)
        return

    # Make subfolder
    safe_title = sanitize_filename(title)
    subfolder = os.path.join(STRM_FOLDER, f"{safe_title} [tmdbid-{tmdb_id}]")
    os.makedirs(subfolder, exist_ok=True)

    # Track number of changes
    changes_count = 0

    for d in hubcloud_links:
        custom_title = d.get("custom_title", "untitled")
        download_url = d.get("download_link")
        if not download_url:
            continue

        safe_filename = sanitize_filename(custom_title) + ".strm"
        path = os.path.join(subfolder, safe_filename)
        new_content = PREFIX + download_url

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                old_content = f.read().strip()

            if old_content != new_content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                # print(f"♻️ Updated: {safe_filename}")
                changes_count += 1
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            # print(f"➕ Created: {safe_filename}")
            changes_count += 1

    # Final summary
    if changes_count == 0:
        # print(f"ℹ️ No changes for {title} [tmdbid-{tmdb_id}]")
        pass
    else:
        msg = f"✅ {title} [tmdbid-{tmdb_id}] - Added/Updated {changes_count} files - XDMovies"
        print(msg)
        send_telegram_message(msg)

# ---------- MAIN LOOP ----------
def monitor_movies():
    os.makedirs(STRM_FOLDER, exist_ok=True)

    while True:
        try:
            print("🔄 Checking latest movies...")

            # Fetch latest list
            headers = HEADERS_BASE.copy()
            headers["referer"] = "https://xdmovies.site/index.html"
            r = requests.get(API_URL, headers=headers)
            r.raise_for_status()
            items = r.json()

            # Filter only movies and take top N
            movies = [i for i in items if i.get("type") == "movie"][:CHECK_LIMIT]

            for item in movies:
                tmdb_id = item.get("tmdb_id")
                if not tmdb_id:
                    continue

                try:
                    details = fetch_movie_details(tmdb_id)
                    create_strm_files(details)
                except Exception as e:
                    print(f"❌ Failed movie {tmdb_id}: {e}")

        except Exception as e:
            print(f"❌ Monitor error: {e}")

        print(f"⏳ Sleeping {CHECK_INTERVAL//60} minutes...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_movies()

