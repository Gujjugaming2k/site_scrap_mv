import urllib.parse
from typing import Dict, List, Optional, Any, Set
import requests

VIDEASY_API_BASE = "https://api.speedracelight.com"
DECRYPTION_API_URL = "https://enc-dec.app/api/dec-videasy"
TMDB_API_KEY = "8476a7ab80ad76f0936744df0430e67c"

class VideasyServer:
    def __init__(
        self,
        display_name: str,
        path: str,
        lang_code: str,  # "en" or "hi"
        lang_name: str,  # "English" or "Hindi"
        movie_only: bool = False,
        may_have_4k: bool = False,
        quality_filter: Optional[str] = None,
        language: Optional[str] = None,
        audio_label: Optional[str] = None
    ):
        self.display_name = display_name
        self.path = path
        self.lang_code = lang_code
        self.lang_name = lang_name
        self.movie_only = movie_only
        self.may_have_4k = may_have_4k
        self.quality_filter = quality_filter
        self.language = language
        self.audio_label = audio_label

# Filtered specifically for English and Hindi sources
VIDEASY_SERVERS = [
    # English Servers
    VideasyServer("Yoru", "cdn", lang_code="en", lang_name="English", movie_only=True, may_have_4k=True, audio_label="Original"),
    VideasyServer("Breach", "m4uhd", lang_code="en", lang_name="English", audio_label="Original"),
    VideasyServer("Neon", "vsrc", lang_code="en", lang_name="English", audio_label="Original"),
    VideasyServer("Vyse", "hdmovie", lang_code="en", lang_name="English", quality_filter="English", audio_label="Original"),
    # Hindi Server
    VideasyServer("Fade", "hdmovie", lang_code="hi", lang_name="Hindi", quality_filter="Hindi", audio_label="Hindi"),
]

class CinebyExtractor:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    @staticmethod
    def double_encode(s: str) -> str:
        """Applies double URL percent-encoding matching Kotlin's pctEncode(pctEncode(s))."""
        return urllib.parse.quote(urllib.parse.quote(s, safe=''), safe='')

    def get_seed(self, tmdb_id: str, headers: Dict[str, str]) -> str:
        seed_url = f"{VIDEASY_API_BASE}/seed?mediaId={tmdb_id}"
        resp = self.session.get(seed_url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json().get("seed", "")

    def get_cinemeta_meta(self, media_type: str, imdb_id: str) -> Dict[str, Any]:
        """Fetch title, year, and metadata from Cinemeta."""
        c_type = "movie" if media_type == "movie" else "series"
        url = f"https://v3-cinemeta.strem.io/meta/{c_type}/{imdb_id}.json"
        try:
            r = self.session.get(url, timeout=5).json()
            return r.get("meta", {})
        except Exception:
            return {}

    def imdb_to_tmdb(self, imdb_id: str, is_movie: bool = True) -> Optional[str]:
        """Resolves IMDB ID (e.g. tt15047880) to TMDB ID using TMDB API."""
        url = f"https://api.tmdb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            r = self.session.get(url, headers=headers, timeout=5).json()
            results = r.get("movie_results" if is_movie else "tv_results", [])
            if results:
                return str(results[0]["id"])
        except Exception:
            pass
        return None

    def extract_videos(
        self,
        path: str,  # Format: "movie/{tmdbId}" or "tv/{tmdbId}/{seasonId}/{episodeId}"
        title: str,
        year: str,
        imdb_id: str = "",
        base_url: str = "https://player.videasy.to",
        sub_limit: int = 5,
    ) -> List[Dict[str, Any]]:
        path_parts = path.split("/")
        is_movie = path_parts[0] == "movie"
        tmdb_id = path_parts[1]
        season_id = "1" if is_movie else path_parts[2]
        episode_id = "1" if is_movie else path_parts[3]

        eligible_servers = [
            s for s in VIDEASY_SERVERS
            if (not s.movie_only or is_movie)
        ]

        if not eligible_servers:
            return []

        backend_headers = {
            "Referer": f"{base_url}/",
            "Origin": base_url,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        seed = self.get_seed(tmdb_id, backend_headers)
        results = []

        for server in eligible_servers:
            try:
                query_params = {
                    "title": self.double_encode(title),
                    "mediaType": "movie" if is_movie else "tv",
                    "year": year,
                    "episodeId": episode_id,
                    "seasonId": season_id,
                    "tmdbId": tmdb_id,
                    "enc": "2",
                    "seed": seed,
                }
                if imdb_id:
                    query_params["imdbId"] = imdb_id
                if server.language:
                    query_params["language"] = server.language

                param_str = "&".join([f"{k}={v}" for k, v in query_params.items()])
                server_url = f"{VIDEASY_API_BASE}/{server.path}/sources-with-title?{param_str}"

                resp = self.session.get(server_url, headers=backend_headers, timeout=10)
                resp.raise_for_status()
                encrypted_text = resp.text

                dec_payload = {
                    "text": encrypted_text,
                    "id": tmdb_id,
                    "seed": seed
                }
                dec_resp = self.session.post(DECRYPTION_API_URL, json=dec_payload, timeout=10)
                dec_resp.raise_for_status()
                decrypted_data = dec_resp.json().get("result", {})

                sources = decrypted_data.get("sources", [])
                if sources and server.quality_filter:
                    sources = [s for s in sources if s.get("quality", "").lower() == server.quality_filter.lower()]

                raw_subs = decrypted_data.get("subtitles", [])
                formatted_subs = []
                for sub in raw_subs:
                    if sub.get("url") and sub.get("language"):
                        # Keep English or Hindi subtitles or top subs
                        formatted_subs.append({
                            "id": sub["language"].lower(),
                            "url": sub["url"],
                            "lang": sub["language"]
                        })
                formatted_subs = formatted_subs[:sub_limit]

                if sources:
                    for src in sources:
                        results.append({
                            "server": server.display_name,
                            "lang_code": server.lang_code,
                            "lang_name": server.lang_name,
                            "quality": src.get("quality", "Auto"),
                            "url": src.get("url"),
                            "subtitles": formatted_subs,
                            "headers": backend_headers,
                        })
                elif decrypted_data.get("streams"):
                    for q, u in decrypted_data["streams"].items():
                        results.append({
                            "server": server.display_name,
                            "lang_code": server.lang_code,
                            "lang_name": server.lang_name,
                            "quality": q,
                            "url": u,
                            "subtitles": formatted_subs,
                            "headers": backend_headers,
                        })
                elif decrypted_data.get("url"):
                    results.append({
                        "server": server.display_name,
                        "lang_code": server.lang_code,
                        "lang_name": server.lang_name,
                        "quality": "Auto",
                        "url": decrypted_data["url"],
                        "subtitles": formatted_subs,
                        "headers": backend_headers,
                    })

            except Exception:
                continue

        return results

    def get_stremio_streams(self, media_type: str, stremio_id: str) -> List[Dict[str, Any]]:
        """
        Converts Stremio ID (e.g. tt15047880 or tmdb:1275779 or series tt0944947:1:2)
        into Stremio-formatted stream objects.
        """
        is_movie = media_type == "movie"
        parts = stremio_id.split(":")
        
        tmdb_id = None
        imdb_id = ""
        season = "1"
        episode = "1"

        if parts[0].startswith("tmdb"):
            tmdb_id = parts[1]
            if not is_movie and len(parts) >= 4:
                season = parts[2]
                episode = parts[3]
        else:
            imdb_id = parts[0]
            if not is_movie and len(parts) >= 3:
                season = parts[1]
                episode = parts[2]

        # Resolve metadata from Cinemeta if imdb_id available
        meta = self.get_cinemeta_meta(media_type, imdb_id) if imdb_id else {}
        title = meta.get("name", "")
        year = str(meta.get("year", ""))

        if not tmdb_id and imdb_id:
            tmdb_id = self.imdb_to_tmdb(imdb_id, is_movie)

        if not tmdb_id:
            return []

        path = f"movie/{tmdb_id}" if is_movie else f"tv/{tmdb_id}/{season}/{episode}"
        
        videos = self.extract_videos(
            path=path,
            title=title,
            year=year,
            imdb_id=imdb_id
        )

        stremio_streams = []
        for v in videos:
            lang_flag = "🇬🇧" if v["lang_code"] == "en" else "🇮🇳"
            stream_title = f"Videasy • {v['server']} [{v['quality']}]\n🔊 Audio: {v['lang_name']}"
            if v["subtitles"]:
                stream_title += f" • 💬 Subs ({len(v['subtitles'])})"

            stremio_stream = {
                "name": f"Videasy {lang_flag} [{v['lang_code'].upper()}]",
                "title": stream_title,
                "url": v["url"],
                "behaviorHints": {
                    "notImportant": False,
                    "proxyHeaders": {
                        "request": {
                            "Referer": v["headers"]["Referer"],
                            "Origin": v["headers"]["Origin"],
                            "User-Agent": v["headers"]["User-Agent"],
                        }
                    }
                }
            }
            if v["subtitles"]:
                stremio_stream["subtitles"] = v["subtitles"]

            stremio_streams.append(stremio_stream)

        return stremio_streams
