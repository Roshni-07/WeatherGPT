from pathlib import Path
from dotenv import load_dotenv

# Load .env explicitly before anything else imports, since services read
# their keys via os.getenv() at import time.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import os  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.routers import advisory, alerts, auth, geocode, map as map_router, places, query, route, sky, weather  # noqa: E402
from app.services import gemini_service, openmeteo  # noqa: E402

app = FastAPI(title="WeatherGPT API", version="2.0")

# Dev/demo only: lock this down to specific origins before real deployment.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(query.router, prefix="/query", tags=["chat"])
app.include_router(weather.router, prefix="/weather", tags=["weather"])
app.include_router(advisory.router, prefix="/advisory", tags=["advisory"])
app.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
app.include_router(map_router.router, prefix="/map", tags=["map"])
app.include_router(route.router, prefix="/route", tags=["route"])
app.include_router(places.router, prefix="/places", tags=["places"])
app.include_router(sky.router, prefix="/sky", tags=["sky"])
app.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/config")
def health_config():
    """Which optional pieces are active (never returns key values)."""
    return {
        "weather_data": "demo (synthetic)" if openmeteo.is_mock() else "live (Open-Meteo, no key needed)",
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "gemini_working": gemini_service.available(),
        "openweathermap_key_set": bool(os.getenv("OPENWEATHERMAP_API_KEY")),
        "google_client_id_set": bool(os.getenv("GOOGLE_CLIENT_ID")),
    }
