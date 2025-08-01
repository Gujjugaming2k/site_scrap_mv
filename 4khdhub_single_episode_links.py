import requests
from bs4 import BeautifulSoup
import os
import re
import base64
import codecs
import json
import time

PROCESSED_FILE = "/tmp/opt/jellyfin/STRM/m3u8/hdhub4u/Series/processed_movies.json"
STRM_2160_DIR = "/tmp/opt/jellyfin/STRM/m3u8/4k_hubcloud/Movies/"
STRM_1080_DIR = "/tmp/opt/jellyfin/STRM/m3u8/hdhub4u/Series/"
STRM_DEFAULT_DIR = "/tmp/opt/jellyfin/STRM/m3u8/hdhub4u/Series/"

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

def get_series_and_season_path(soup, filename):
    # Extract series name from <h1 class="page-title">
    title_tag = soup.find("h1", class_="page-title")
    raw_name = title_tag.text.strip() if title_tag else "UnknownSeries"

    # Sanitize folder name
    series_name = re.sub(r"[^\w\s.-]", "", raw_name).strip().replace("  ", " ")
    series_name = series_name.replace("’", "'")  # optional, handle curly apostrophes

    # Detect season from filename
    match = re.search(r"\bS(?:eason)?0?(\d{1,2})\b", filename, re.IGNORECASE)
    if not match:
        match = re.search(r"S(\d{1,2})E\d{1,2}", filename)

    season = f"S{match.group(1).zfill(2)}" if match else "SeasonUnknown"

    # Create full path
    folder_path = os.path.join(STRM_1080_DIR, series_name, season)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path



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

def get_single_episode_links(movie_url):
    full_url = "https://4khdhub.fans" + movie_url
    response = requests.get(full_url)
    soup = BeautifulSoup(response.content, "html.parser")

    episodes_tab = soup.select("#episodes .episode-download-item")
    collected_links = []
    codec_tracker = {}

    for item in episodes_tab:
        file_title_el = item.select_one(".episode-file-title")
        if not file_title_el:
            continue

        file_title = file_title_el.text.strip()
        if "1080p" not in file_title:
            continue

        # Match codec using '264' or '265'
        if "264" in file_title:
            codec = "H.264"
        elif "265" in file_title:
            codec = "H.265"
        else:
            codec = None

        if not codec:
            continue

        # Prefer H.264 if duplicate episode exists
        episode_id = re.search(r"S\d{1,2}E\d{1,2}", file_title)
        key = episode_id.group(0) if episode_id else file_title
        if codec == "H.265" and codec_tracker.get(key) == "H.264":
            continue
        codec_tracker[key] = codec

        anchors = item.select(".episode-links a")
        for anchor in anchors:
            label = anchor.text.strip()
            if "HubCloud" in label:
                short_url = anchor["href"]
                final_url = extract_and_decode_final_link(short_url)
                if final_url:
                    collected_links.append((file_title, final_url))
                break

    return collected_links, soup



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
    url = f"https://4khdhub.fans/category/series-10811.html/page/1.html"
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

def create_strm_file(filename, url, soup):
    strm_dir = get_series_and_season_path(soup, filename)
    path = os.path.join(strm_dir, f"{filename}.strm")
    modified_url = f"https://hubcloud-r2-dev.hdmovielover.workers.dev/download?url={url}"

    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(modified_url)
        print(f"✅ .strm created: {filename} → {strm_dir}")
        return strm_dir, filename
    else:
        print(f"⚠️ Skipped (already exists): {filename}")
        return None, None

def get_grouped_episode_links(movie_url):
    full_url = "https://4khdhub.fans" + movie_url
    response = requests.get(full_url)
    soup = BeautifulSoup(response.content, "html.parser")

    season_sections = soup.select(".season-content .season-item.episode-item")
    collected_links = []
    codec_tracker = {}

    for section in season_sections:
        # Extract group header like "S01 1080p BluRay x265"
        header_el = section.select_one(".episode-title")
        header_text = header_el.text.strip() if header_el else ""

        # Determine fallback codec from season header
        default_codec = None
        if re.search(r"265|x265|HEVC", header_text, re.IGNORECASE):
            default_codec = "H.265"
        elif re.search(r"264|x264|AVC|H\.264", header_text, re.IGNORECASE):
            default_codec = "H.264"

        download_blocks = section.select(".episode-downloads .episode-download-item")
        for item in download_blocks:
            title_el = item.select_one(".episode-file-title")
            if not title_el:
                continue

            file_title = title_el.text.strip()
            if "1080p" not in file_title:
                continue

            # Try direct codec detection from filename
            if re.search(r"264|x264|AVC|H\.264", file_title, re.IGNORECASE):
                codec = "H.264"
            elif re.search(r"265|x265|HEVC", file_title, re.IGNORECASE):
                codec = "H.265"
            else:
                codec = default_codec  # Fallback to group header codec

            if not codec:
                continue

            episode_id = re.search(r"S\d{1,2}E\d{1,2}", file_title)
            key = episode_id.group(0) if episode_id else file_title

            # Prefer H.264 over H.265 if duplicate episode
            if codec == "H.265" and codec_tracker.get(key) == "H.264":
                continue
            codec_tracker[key] = codec

            # Get HubCloud link
            links = item.select(".episode-links a")
            for link in links:
                label = link.text.strip()
                if "HubCloud" in label:
                    short_url = link["href"]
                    final_url = extract_and_decode_final_link(short_url)
                    if final_url:
                        collected_links.append((file_title, final_url))
                    break  # only grab one HubCloud per episode

    return collected_links, soup

        
def monitor():
    while True:
        print("\n🔄 Checking for updates...")
        processed = load_processed_data()

        try:
            movie_urls = get_movie_list()

            for movie_url in movie_urls:
                print(f"\n📄 Processing {movie_url}")
                full_url = "https://4khdhub.fans" + movie_url
                response = requests.get(full_url)
                soup = BeautifulSoup(response.content, "html.parser")

                # Dynamically select parser based on structure
                if soup.select(".season-content .episode-item"):
                    hubcloud_links, soup = get_grouped_episode_links(movie_url)
                elif soup.select("#episodes .episode-download-item"):
                    hubcloud_links, soup = get_single_episode_links(movie_url)
                else:
                    print(f"⚠️ Unknown page layout, skipping: {movie_url}")
                    continue

                old_links = processed.get(movie_url, [])
                new_links = []
                season_batches = {}

                for file_title, final_url in hubcloud_links:
                    if final_url not in old_links:
                        season_folder, written_file = create_strm_file(file_title, final_url, soup)
                        new_links.append(final_url)

                        if season_folder and written_file:
                            season_batches.setdefault(season_folder, []).append(written_file)

                # Batch Telegram messages by season
                for season_path, files in season_batches.items():
                    movie_name = os.path.basename(os.path.dirname(season_path))
                    season_name = os.path.basename(season_path)
                    count = len(files)

                    message = (
                        f"📦 Series Added: *{movie_name}* - `{season_name}` ({count} episodes)\n"
                        f"📁 Location: `{season_path}`"
                    )
                    send_telegram_message(message)

                if new_links:
                    processed[movie_url] = list(set(old_links + new_links))
                    save_processed_data(processed)

        except Exception as e:
            print(f"❌ Error during monitoring: {e}")

        print(f"\n⏳ Waiting {CHECK_INTERVAL // 60} minutes before next check...")
        time.sleep(CHECK_INTERVAL)



if __name__ == "__main__":
    monitor()
