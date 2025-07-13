import requests
from bs4 import BeautifulSoup
import os
import re
import base64
import codecs
import json
import time

PROCESSED_FILE = "processed_movies.json"
STRM_2160_DIR = "Movies/"
STRM_1080_DIR = "Movies/"
STRM_DEFAULT_DIR = "m3u8/"

CHECK_INTERVAL = 600  # 10 minutes

BOT_TOKEN = "7531637845:AAEHIucLbu41bf08ckwGAr-fjF-BPBYNB_Q"
CHANNEL_ID="-1002873454819"
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

def extract_final_hubcloud_link_from_hblinks(hblinks_url):
    response = requests.get(hblinks_url)
    soup = BeautifulSoup(response.content, "html.parser")

    for a_tag in soup.find_all("a", href=True):
        href = a_tag['href']
        # Look for direct HubCloud links
        if "https://hubcloud.one/drive/" in href:
            return f"{href}"

    print(f"❌ No HubCloud link found on: {hblinks_url}")
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

def get_hdhub4u_links():
    url = "https://hdhub4u.family/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    movie_links = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag['href']
        # Only include links that contain "full-movie"
        if href.startswith("https://hdhub4u.family/") and "full-movie" in href.lower():
            movie_links.append(href)

    return movie_links[::-1]


def get_hubcloud_links(movie_url):
    full_url = movie_url if movie_url.startswith("http") else "https://hdhub4u.family" + movie_url
    response = requests.get(full_url)
    soup = BeautifulSoup(response.content, "html.parser")

    filename_base = extract_movie_title_and_year(soup)

    x264_link = None
    x265_link = None

    for h3_tag in soup.find_all("h3"):
        a_tag = h3_tag.find("a", href=True)
        if a_tag:
            text = a_tag.get_text(strip=True)
            href = a_tag['href']

            if "1080p" in text:
                final_url = extract_and_decode_final_link(href)
                if final_url:
                    if "x264" in text.lower():
                        x264_link = (filename_base, final_url)
                    elif "x265" in text.lower():
                        x265_link = (filename_base, final_url)

    if x264_link:
        return [x264_link]
    elif x265_link:
        return [x265_link]
    else:
        return []


def extract_movie_title_and_year(soup):
    import re

    # Grab movie title from og:title meta tag or fallback to <title>
    meta_tag = soup.find("meta", property="og:title")
    title_text = meta_tag['content'] if meta_tag else soup.title.string

    # Extract title and year → e.g. "Dhadak (2018)" from full title
    title_match = re.search(r"^(.*)\((\d{4})\)", title_text)
    if title_match:
        movie_name = title_match.group(1).strip()
        movie_year = title_match.group(2)

        # Replace disallowed characters with space, collapse multiple spaces
        safe_name = re.sub(r'[\\/*?:"<>|]', " ", movie_name)
        safe_name = re.sub(r'\s+', ' ', safe_name).strip()

        return f"{safe_name} {movie_year}"

    return "Unknown_Title"




def create_strm_file(filename, url):
    strm_dir = get_strm_dir(filename)
    path = os.path.join(strm_dir, f"{filename}.strm")

    # Wrap original URL
    wrapped_url = extract_final_hubcloud_link_from_hblinks(url)
    modified_url = f"https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url={wrapped_url}"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(modified_url)
        print(f"✅ .strm created: {filename} → {strm_dir}")

        # Send Telegram message with dynamic content
        send_telegram_message(f"*{filename}* added in `{strm_dir}`")
    else:
        print(f"⚠️ Skipped (already exists): {filename}")
     
def monitor():

    while True:
        print("\n🔄 Checking for updates...")
        processed = load_processed_data()
        try:
            movie_urls = get_hdhub4u_links()

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
