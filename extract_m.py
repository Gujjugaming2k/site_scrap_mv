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

    season_id = get_season_id(show_url)
    if not season_id:
        return jsonify({"error": "No season id found"}), 404

    # --- Cursor-based pagination ---
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

        # Print API URL for debugging
        print(f"[DEBUG] API URL: {api_url}")

        try:
            resp = requests.get(api_url, timeout=10).json()
        except Exception as e:
            return jsonify({
                "show_url": show_url,
                "season_id": season_id,
                "error": f"Failed to fetch API: {str(e)}",
                "api_url": api_url
            }), 500

        items = resp.get("items")
        if not items:
            print("[DEBUG] No items found in response:", resp)
            break
        
        for idx, item in enumerate(items, start=len(episodes)+1):
            title = item.get("title")
            hls_link = item.get("stream", {}).get("hls", {}).get("high")
            if title and hls_link:
                if not hls_link.startswith("http"):
                    hls_link = f"https://d3sgzbosmwirao.cloudfront.net/{hls_link}"
                episodes.append({"title": title, "hls": hls_link, "ep_num": idx})


        # Get next cursor
        next_cursor = resp.get("next")
        if not next_cursor:
            break  # all episodes fetched

    return jsonify({
        "show_url": show_url,
        "season_id": season_id,
        "episodes": episodes
    })


import os

@app.route("/save")
def save_strm():
    show_url = request.args.get("url")
    if not show_url:
        return jsonify({"error": "Please provide ?url="}), 400

    # --- Get season ID ---
    season_id = get_season_id(show_url)
    if not season_id:
        return jsonify({"error": "No season id found"}), 404

    # --- Extract series title from main page ---
    try:
        html = requests.get(show_url, timeout=10).text
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1")  # Usually main title is in <h1>
        series_title = title_tag.text.strip() if title_tag else "UnknownSeries"
        # Clean folder name
        series_title = "".join(c for c in series_title if c.isalnum() or c in " _-")
    except Exception:
        series_title = "UnknownSeries"

    # --- Cursor-based pagination to get all episodes ---
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
                "show_url": show_url,
                "season_id": season_id,
                "error": f"Failed to fetch API: {str(e)}",
                "api_url": api_url
            }), 500

        items = resp.get("items", [])  # Safe default to empty list
        if not items:
            break

        for idx, item in enumerate(items, start=len(episodes)+1):
            title = item.get("title")
            hls_link = item.get("stream", {}).get("hls", {}).get("high")
            if title and hls_link:
                if not hls_link.startswith("http"):
                    hls_link = f"https://d3sgzbosmwirao.cloudfront.net/{hls_link}"
                episodes.append({"title": title, "hls": hls_link, "ep_num": idx})

        # Get next cursor
        next_cursor = resp.get("next")
        if not next_cursor:
            break  # all episodes fetched

    if not episodes:
        return jsonify({"error": "No episodes found", "show_url": show_url, "season_id": season_id})

    # --- Create folder ---
    folder_path = os.path.join("/tmp/opt/jellyfin/STRM/m3u8/mxplayer/Series/", series_title)
    os.makedirs(folder_path, exist_ok=True)

    # --- Save .strm files ---
    saved_files = []
    for ep in episodes:
        file_name = f"EP{ep['ep_num']}.strm"
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(ep["hls"])
        saved_files.append(file_path)

    return jsonify({
        "series": series_title,
        "season_id": season_id,
        "saved_files": saved_files,
        "total_episodes": len(episodes)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

