import requests
from bs4 import BeautifulSoup
import base64
import codecs
import json
import re
import os
import json
import time

BASE_URL = "https://hdhub4u.gifts/"
SSL_STATUS = False # True or False only
FOLDER_PATH = "/tmp/opt/jellyfin/STRM/m3u8/GDriveSharer/HubCloudProxy/Movies/"  # You can change this as needed
PROCESSED_FILE = "/tmp/opt/jellyfin/STRM/m3u8/GDriveSharer/HubCloudProxy/processed.json"
PREFIX = "https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url="
# Telegram Notification Config
TELEGRAM_BOT_TOKEN = "7531637845:AAEHIucLbu41bf08ckwGAr-fjF-BPBYNB_Q"
TELEGRAM_CHAT_ID = "-1002873454819"

HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
}

os.makedirs(FOLDER_PATH, exist_ok=True)  # Ensure output folder exists

def load_processed():
    if not os.path.exists(PROCESSED_FILE):
        return []
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_processed(processed_urls):
    with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
        json.dump(processed_urls, f, indent=2)

#-------------------Shortner Bypass Start----------------------

def extract_and_decode_final_link(short_url):
    try:
        response = requests.get(short_url, timeout=120)
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

#-------------------Shortner Bypass End----------------------

def is_movie(title: str) -> bool:
    title_lower = title.lower()
    return "season" not in title_lower and "episodes" not in title_lower

def extract_movies():
    response = requests.get(BASE_URL, headers=HEADERS, verify=SSL_STATUS, timeout=120)
    if response.status_code != 200:
        print(f"❌ Failed to fetch page. Status: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    movie_list = []

    for li in soup.select("ul.recent-movies li"):
        figcaption = li.find("figcaption")
        if not figcaption:
            continue

        a_tag = figcaption.find("a")
        p_tag = a_tag.find("p") if a_tag else None

        if a_tag and p_tag:
            url = a_tag["href"]
            title = p_tag.text.strip()

            if is_movie(title):
                movie_list.append({
                    "title": title,
                    "url": url
                })

    return list(reversed(movie_list))  # Latest first

# -------------------- HANDLER FUNCTIONS --------------------

def handle_hubcloud(link):
    print(f"🌐 HubCloud URL: {link}")
    title = fetch_hubcloud_title(link)
    if title:
        return create_strm_file(title, link)
    return False

def handle_hubdrive(link):
    print(f"🌐 HubDrive URL: {link}")
    try:
        resp = requests.get(link, headers=HEADERS, timeout=120)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all("a", href=True):
            if "hubcloud.one" in a["href"]:
                return handle_hubcloud(a["href"])
    except Exception as e:
        print(f"❌ Error while processing HubDrive: {e}")
    print("⚠️ HubCloud link not found in HubDrive page.")
    return None

def handle_hblinks(link):
    print(f"🌐 HBLinks URL: {link}")
    try:
        resp = requests.get(link, headers=HEADERS, timeout=120)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "hubcloud.one" in href:
                return handle_hubcloud(href)
            elif "hubdrive.wales" in href:
                return handle_hubdrive(href)
    except Exception as e:
        print(f"❌ Error while processing HBLinks: {e}")
    print("⚠️ HubCloud/HubDrive link not found in HBLinks page.")
    return None

def handle_techyboy(link):
    print(f"🔗 Short Link Detected: {link}")
    decoded_url = extract_and_decode_final_link(link)
    if not decoded_url:
        print("❌ Failed to decode short link.")
        return None

    print(f"🔓 Decoded URL: {decoded_url}")

    if "hubcloud.one" in decoded_url:
        return handle_hubcloud(decoded_url)
    elif "hubdrive.space" in decoded_url:
        return handle_hubdrive(decoded_url)
    elif "hblinks.pro/archives/" in decoded_url:
        return handle_hblinks(decoded_url)
    else:
        print("⚠️ Decoded link is unknown type.")
        return None

def handle_unsupported_link(title, page_url=None, unsupported_link=None):
    print(f"🚫 Unsupported download link found for movie: {title}")
    if page_url:
        print(f"🧭 Page URL: {page_url}")
    if unsupported_link:
        print(f"🔗 Unsupported Link: {unsupported_link}")
    print("⚠️ Please check manually for supported formats.\n")
    message = f"🚫 Unsupported Download Link: {unsupported_link} for Movie {title} Visit {page_url} and Upload Manually @tgH2R3 and @VFlix_admin_1"
    send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)

def handle_unknown(title, page_url=None):
    print(f"🚫 No valid 1080p section found for movie: {title}")
    if page_url:
        print(f"🧭 Page URL: {page_url}")
    print("⚠️ Skipped due to unknown structure or missing quality.\n")

# -------------------- FETCH HUBCLOUD TITLE --------------------

def fetch_hubcloud_title(hubcloud_url):
    try:
        print(f"🌐 Fetching title from HubCloud: {hubcloud_url}")
        resp = requests.get(hubcloud_url, headers=HEADERS, timeout=120)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch hubcloud URL. Status: {resp.status_code}")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.text.strip()
            print(f"🎬 Extracted Title: {title}")
            return title
        else:
            print("⚠️ Title tag not found.")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching title: {e}")
        return None

def create_strm_file(title, hubcloud_url):
    try:
        safe_filename = "".join(c for c in title if c.isalnum() or c in "._- ").strip()
        file_path = os.path.join(FOLDER_PATH, f"{safe_filename}.strm")
        stream_url = f"{PREFIX}{hubcloud_url}"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(stream_url + "\n")

        print(f"📁 STRM file created: {file_path}")
        message = f"🇮🇳 {title} - Uploaded from HDHub4u"
        send_telegram_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
        return True
    except Exception as e:
        print(f"❌ Failed to create .strm file: {e}")
        return False

def send_telegram_message(bot_token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=payload, timeout=120)
        if response.status_code == 200:
            print("📩 Telegram message sent.")
        else:
            print(f"❌ Failed to send Telegram message. Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")

# -------------------- MAIN SCRAPE LOGIC --------------------

def extract_1080p_x264_links(movie_title, page_url):
    print(f"🔍 Checking: {page_url}")
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=120, verify=SSL_STATUS)
        if resp.status_code != 200:
            print(f"❌ Failed to fetch detail page. Status: {resp.status_code}")
            return False

        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all("a", href=True):
            anchor_text = a.get_text(strip=True)

            if "1080p x264" in anchor_text.lower() or "1080p Links" in anchor_text:
                link = a["href"]
                if "hubcloud.one" in link:
                    return handle_hubcloud(link)
                elif "hubdrive.wales" in link:
                    return handle_hubdrive(link)
                elif "hblinks.pro/archives/" in link:
                    return handle_hblinks(link)
                elif "techyboy4u.com/?id=" in link:
                    return handle_techyboy(link)
                elif "taazabull24.com/?id=" in link:
                    return handle_techyboy(link)
                else:
                    handle_unsupported_link(movie_title, page_url=page_url, unsupported_link=link)
                    return False

        handle_unknown(movie_title, page_url=page_url)
        return False

    except Exception as e:
        print(f"⚠️ Error while processing page: {e}")
        return False

def main_loop():

    while True:
        print(f"\n🔁 Checking for new movies...")
        processed_urls = load_processed()
        movies = extract_movies()
        new_processed = False

        for movie in movies:
            if movie['url'] in processed_urls:
                continue

            print(f"\n🎬 {movie['title']}")
            success = extract_1080p_x264_links(movie['title'], movie['url'])

            if success:
                processed_urls.append(movie['url'])
                save_processed(processed_urls)
                new_processed = True
            else:
                print("⚠️ Skipped: Could not process this movie.\n")

        if not new_processed:
            print("✅ No new movies to process.")
        print("⏳ Waiting 60 seconds...\n")
        time.sleep(600)

# -------------------- RUN SCRIPT --------------------

if __name__ == "__main__":
    main_loop()
