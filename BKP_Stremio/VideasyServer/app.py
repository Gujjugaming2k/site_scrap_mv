from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from cineby_extractor import CinebyExtractor

app = FastAPI(title="Videasy Stremio Addon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = CinebyExtractor()

MANIFEST = {
    "id": "com.videasy.stremio.addon",
    "version": "1.0.0",
    "name": "Videasy (EN & HI)",
    "description": "Stremio addon serving high-quality English & Hindi streams from Videasy.",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt", "tmdb"],
    "catalogs": [],
    "logo": "https://cdn-icons-png.flaticon.com/512/1179/1179120.png"
}

@app.get("/")
def landing_page():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Videasy Stremio Addon (EN & HI)</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                color: #f8fafc;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }
            .card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 20px;
                padding: 2.5rem;
                max-width: 550px;
                width: 100%;
                text-align: center;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }
            .badge-container {
                display: flex;
                justify-content: center;
                gap: 0.5rem;
                margin-bottom: 1rem;
            }
            .badge {
                background: rgba(99, 102, 241, 0.2);
                color: #a5b4fc;
                border: 1px solid rgba(99, 102, 241, 0.3);
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.85rem;
                font-weight: 600;
            }
            h1 {
                font-size: 2.2rem;
                font-weight: 700;
                margin-bottom: 0.75rem;
                background: linear-gradient(to right, #818cf8, #c084fc);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            p {
                color: #94a3b8;
                font-size: 0.95rem;
                line-height: 1.6;
                margin-bottom: 1.5rem;
            }
            .btn {
                display: inline-block;
                width: 100%;
                padding: 0.85rem 1.5rem;
                background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                color: #ffffff;
                text-decoration: none;
                font-weight: 600;
                border-radius: 12px;
                transition: all 0.2s ease;
                box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4);
                margin-bottom: 1rem;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 15px 25px -5px rgba(99, 102, 241, 0.5);
            }
            .manifest-url {
                background: rgba(0, 0, 0, 0.3);
                padding: 0.75rem;
                border-radius: 8px;
                font-family: monospace;
                font-size: 0.85rem;
                color: #cbd5e1;
                word-break: break-all;
                cursor: pointer;
            }
            .footer {
                margin-top: 1.5rem;
                font-size: 0.8rem;
                color: #64748b;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="badge-container">
                <span class="badge">🇬🇧 English</span>
                <span class="badge">🇮🇳 Hindi</span>
            </div>
            <h1>Videasy Stremio Addon</h1>
            <p>Provides fast, high-quality streams from Videasy servers formatted directly for Stremio.</p>
            <a id="install-btn" href="#" class="btn">⚡ Install Addon on Stremio</a>
            <div class="manifest-url" onclick="navigator.clipboard.writeText(window.location.origin + '/manifest.json'); alert('Manifest URL copied!');">
                Click to copy manifest URL
            </div>
            <div class="footer">
                Videasy Addon v1.0.0 • Python & FastAPI
            </div>
        </div>
        <script>
            const manifestUrl = window.location.origin + '/manifest.json';
            const stremioUrl = 'stremio://' + window.location.host + '/manifest.json';
            document.getElementById('install-btn').href = stremioUrl;
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/manifest.json")
def get_manifest():
    return JSONResponse(content=MANIFEST)

@app.get("/stream/{type}/{id}.json")
def get_streams(type: str, id: str):
    """
    Stremio stream endpoint:
    - type: "movie" or "series"
    - id: "tt15047880" or "tmdb:1275779" or "tt0944947:1:1"
    """
    streams = extractor.get_stremio_streams(media_type=type, stremio_id=id)
    return JSONResponse(content={"streams": streams})
