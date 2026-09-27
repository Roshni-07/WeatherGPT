from pathlib import Path
from dotenv import load_dotenv

# Load .env explicitly before anything else imports, since services read
# their keys via os.getenv() at import time (module-level constants) --
# relying on `uvicorn --env-file` alone raced against those imports.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import query, alerts, weather, geocode, auth

app = FastAPI(title="WeatherGPT API")

# Dev/demo only: allows the standalone prototype frontend (served on a
# different port) to call this API from the browser. Lock this down to
# specific origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(weather.router, prefix="/weather", tags=["weather"])
app.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/config")
def health_config():
    """Dev-only: confirms which env vars actually loaded, without leaking
    the values themselves. Hit this to sanity-check .env is being read."""
    import os
    return {
        "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
        "OPENWEATHERMAP_API_KEY": bool(os.getenv("OPENWEATHERMAP_API_KEY")),
        "GOOGLE_CLIENT_ID": bool(os.getenv("GOOGLE_CLIENT_ID")),
    }
