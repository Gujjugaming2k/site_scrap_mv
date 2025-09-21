from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- Helper: extract season id from show page ---
def get_season_id(show_url):
    html = requests.get(show_url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    tab = soup.select_one(".seasons-episodes-section .tab-header[data-id]")
    return tab["data-id"] if tab and tab.has_attr("data-id") else None


@app.route("/extract_id")
def extract_id():
    show_url = request.args.get("url")
    if not show_url:
        return jsonify({"error": "Please provide ?url="}), 400

    season_id = get_season_id(show_url)
    if not season_id:
        return jsonify({"error": "No season id found"}), 404

    return jsonify({"show_url": show_url, "season_id": season_id})


@app.route("/extract_stream")
def extract_stream():
    show_url = request.args.get("url")
    if not show_url:
        return jsonify({"error": "Please provide ?url="}), 400

    # --- Extract series title ---
    try:
        html = requests.get(show_url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1")
        series_title = title_tag.text.strip() if title_tag else "UnknownSeries"
        series_title = "".join(c for c in series_title if c.isalnum() or c in " _-")
    except Exception:
        series_title = "UnknownSeries"

    # --- Extract seasons ---
    seasons = get_seasons(show_url)
    if not seasons:
        return jsonify({"error": "No seasons found", "show_url": show_url})

    all_seasons_data = []

    for season in seasons:
        season_id = season["id"]
        season_name = season["title"]

        # Cursor-based pagination for episodes
        episodes = []
        next_cursor = None
        while True:
            api_url = (
                f"https://api.mxplayer.in/v1/web/detail/tab/tvshowepisodes"
                f"?type=season&id={season_id}&device-density=2"
                f"&userid=653e079c-b6e5-438d-a0c6-12416e3f5133"
                f"&platform=com.mxplay.desktop&content-languages=hi,en,gu"
                f"&kids-mode-enabled=false"
            )
            if next_cursor:
                api_url += f"&{next_cursor}"

            print(f"[DEBUG] API URL: {api_url}")
            try:
                resp = requests.get(api_url, timeout=10).json()
            except Exception as e:
                return jsonify({
                    "error": f"Failed to fetch API: {str(e)}",
                    "season_id": season_id,
                    "api_url": api_url
                }), 500

            items = resp.get("items", []) or []
            for idx, item in enumerate(items, start=len(episodes)+1):
                title = item.get("title")
                hls_link = item.get("stream", {}).get("hls", {}).get("high")
                if title and hls_link:
                    if not hls_link.startswith("http"):
                        hls_link = f"https://cdn.mxplayer.in/{hls_link}"
                    episodes.append({"title": title, "hls": hls_link, "ep_num": idx})

            next_cursor = resp.get("next")
            if not next_cursor:
                break

        all_seasons_data.append({
            "season_name": season_name,
            "season_id": season_id,
            "episodes": episodes
        })

    return jsonify({
        "series": series_title,
        "seasons": all_seasons_data
    })



import os

@app.route("/save")
def save_strm():
    show_url = request.args.get("url")
    if not show_url:
        return jsonify({"error": "Please provide ?url="}), 400

    # --- Extract series title ---
    try:
        html = requests.get(show_url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1")
        series_title = title_tag.text.strip() if title_tag else "UnknownSeries"
        series_title = "".join(c for c in series_title if c.isalnum() or c in " _-")
    except Exception:
        series_title = "UnknownSeries"

    # --- Extract seasons ---
    seasons = get_seasons(show_url)
    if not seasons:
        return jsonify({"error": "No seasons found", "show_url": show_url})

    saved_files_all = []

    for season in seasons:
        season_id = season["id"]
        season_name = season["title"]

        # Cursor-based pagination for episodes
        episodes = []
        next_cursor = None
        while True:
            api_url = (
                f"https://api.mxplayer.in/v1/web/detail/tab/tvshowepisodes"
                f"?type=season&id={season_id}&device-density=2"
                f"&userid=653e079c-b6e5-438d-a0c6-12416e3f5133"
                f"&platform=com.mxplay.desktop&content-languages=hi,en,gu"
                f"&kids-mode-enabled=false"
            )
            if next_cursor:
                api_url += f"&{next_cursor}"

            resp = requests.get(api_url, timeout=10).json()
            items = resp.get("items", []) or []
            for idx, item in enumerate(items, start=len(episodes)+1):
                title = item.get("title")
                hls_link = item.get("stream", {}).get("hls", {}).get("high")
                if title and hls_link:
                    if not hls_link.startswith("http"):
                        hls_link = f"https://cdn.mxplayer.in/{hls_link}"
                    episodes.append({"title": title, "hls": hls_link, "ep_num": idx})

            next_cursor = resp.get("next")
            if not next_cursor:
                break

        # --- Save episodes to strm files ---
        folder_path = os.path.join("/tmp/opt/jellyfin/STRM/m3u8/mxplayer", series_title, season_name)
        os.makedirs(folder_path, exist_ok=True)
        saved_files = []
        for ep in episodes:
            file_name = f"EP{ep['ep_num']}.strm"
            file_path = os.path.join(folder_path, file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(ep["hls"])
            saved_files.append(file_path)
        saved_files_all.extend(saved_files)

    return jsonify({
        "series": series_title,
        "seasons": [s["title"] for s in seasons],
        "total_saved_files": len(saved_files_all),
        "saved_files": saved_files_all
    })



def get_seasons(show_url):
    """
    Extract all season IDs and titles from the show page.
    Returns a list of dicts: [{"id": season_id, "title": season_name}, ...]
    """
    html = requests.get(show_url, timeout=10).text
    soup = BeautifulSoup(html, "html.parser")
    seasons = []
    season_divs = soup.select(".seasons-episodes-section .tab-header")
    for div in season_divs:
        season_id = div.get("data-id")
        season_name_tag = div.select_one("h2.h2-heading")
        season_name = season_name_tag.text.strip() if season_name_tag else "SeasonUnknown"
        # Clean folder name
        season_name = "".join(c for c in season_name if c.isalnum() or c in " _-")
        if season_id:
            seasons.append({"id": season_id, "title": season_name})
    return seasons



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5020, debug=True)
