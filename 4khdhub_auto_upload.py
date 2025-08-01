import requests
from bs4 import BeautifulSoup
import os
import re
import base64
import codecs
import json
import time

PROCESSED_FILE = "/tmp/opt/jellyfin/STRM/processed_movies.json"
STRM_2160_DIR = "/tmp/opt/jellyfin/STRM/m3u8/4k_hubcloud/Movies/"
STRM_1080_DIR = "/tmp/opt/jellyfin/STRM/m3u8/hdhub4u/Movies/"
STRM_DEFAULT_DIR = "/tmp/opt/jellyfin/STRM/m3u8/"

CHECK_INTERVAL = 600  # 10 minutes


# Message to send
#MESSAGE="Jellyfin - Installation Started"

# Ensure directories exist
os.makedirs(STRM_2160_DIR, exist_ok=True)
os.makedirs(STRM_1080_DIR, exist_ok=True)
os.makedirs(STRM_DEFAULT_DIR, exist_ok=True)



def get_strm_dir(filename):
    """Choose directory based on quality keyword in filename."""
    if "2160" in filename:
        return STRM_2160_DIR
    elif "1080" in filename:
        return STRM_1080_DIR
    else:
        return STRM_DEFAULT_DIR


def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, data=payload)
        if response.ok:
            print("📢 Telegram message sent!")
        else:
            print(f"⚠️ Telegram error: {response.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")


def load_processed_data():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return json.load(f)
    return {}

def save_processed_data(data):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(data, f, indent=2)

def decode_o(o_val):
    try:
        step1 = base64.b64decode(o_val).decode()
        step2 = base64.b64decode(step1).decode()
        step3 = codecs.encode(step2, 'rot_13')
        step4 = base64.b64decode(step3).decode()
        final_encoded = json.loads(step4).get("o")
        return base64.b64decode(final_encoded).decode()
    except Exception as e:
        print(f"Decoding error: {e}")
        return None

def extract_and_decode_final_link(short_url):
    try:
        response = requests.get(short_url, timeout=10)
        response.raise_for_status()
        html = response.text

        match = re.search(r"s\('o','(.*?)'", html)
        if not match:
            print("No 'o' value found in the HTML.")
            return None

        o_val = match.group(1)
        return decode_o(o_val)

    except Exception as e:
        print(f"❌ Request error: {e}")
        return None

def get_movie_list():
    url = f"https://4khdhub.fans/category/movies-10810.html/page/1.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    movie_cards = soup.find_all("a", class_="movie-card")
    movie_urls = [card['href'] for card in movie_cards if 'href' in card.attrs]
    return movie_urls[::-1]  # Latest first

def get_hubcloud_links(movie_url):
    full_url = "https://4khdhub.fans" + movie_url
    response = requests.get(full_url)
    soup = BeautifulSoup(response.content, "html.parser")

    download_items = soup.find_all("div", class_="download-item")
    links = []

    for item in download_items:
        file_title = item.find("div", class_="file-title").text.strip() if item.find("div", class_="file-title") else None
        grid_div = item.find("div", class_="grid grid-cols-2 gap-2")

        if grid_div:
            anchors = grid_div.find_all("a")
            for anchor in anchors:
                span = anchor.find("span")
                if span and "Download HubCloud" in span.text:
                    short_url = anchor['href']
                    final_url = extract_and_decode_final_link(short_url)
                    if final_url and file_title:
                        links.append((file_title, final_url))

    return links

def create_strm_file(filename, url):
    strm_dir = get_strm_dir(filename)
    path = os.path.join(strm_dir, f"{filename}.strm")

    # Wrap original URL
    modified_url = f"https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url={url}"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(modified_url)
        print(f"✅ .strm created: {filename} → {strm_dir}")

        # Send Telegram message with dynamic content
        send_telegram_message(f"`4khdhub.fans` - *{filename}* added in `{strm_dir}`")
    else:
        print(f"⚠️ Skipped (already exists): {filename}")
def monitor():

    while True:
        print("\n🔄 Checking for updates...")
        processed = load_processed_data()
        try:
            movie_urls = get_movie_list()

            for movie_url in movie_urls:
                print(f"\n📄 Processing {movie_url}")
                hubcloud_links = get_hubcloud_links(movie_url)

                old_links = processed.get(movie_url, [])
                new_links = []

                for file_title, final_url in hubcloud_links:
                    if final_url not in old_links:
                        create_strm_file(file_title, final_url)
                        new_links.append(final_url)

                if new_links:
                    processed[movie_url] = list(set(old_links + new_links))
                    save_processed_data(processed)

        except Exception as e:
            print(f"❌ Error during monitoring: {e}")

        print(f"\n⏳ Waiting {CHECK_INTERVAL // 60} minutes before next check...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor()
