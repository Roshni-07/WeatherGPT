"""
Forward and reverse geocoding via OpenWeatherMap's Geo API (same key as
weather_service, no separate signup needed).

Docs: https://openweathermap.org/api/geocoding-api
"""
import os
import httpx

OWM_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
GEO_BASE = "https://api.openweathermap.org/geo/1.0"


async def search_location(query: str, limit: int = 5) -> list[dict]:
    """Forward geocode a place name typed by the user into candidates."""
    if not OWM_KEY:
        raise RuntimeError("OPENWEATHERMAP_API_KEY is not set")

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{GEO_BASE}/direct",
            params={"q": query, "limit": limit, "appid": OWM_KEY},
        )
        resp.raise_for_status()
        results = resp.json()

    return [
        {
            "name": r.get("name"),
            "state": r.get("state"),
            "country": r.get("country"),
            "lat": r["lat"],
            "lon": r["lon"],
        }
        for r in results
    ]


async def reverse_geocode(lat: float, lon: float) -> dict | None:
    """Turn browser-supplied coordinates into a human-readable place name."""
    if not OWM_KEY:
        raise RuntimeError("OPENWEATHERMAP_API_KEY is not set")

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{GEO_BASE}/reverse",
            params={"lat": lat, "lon": lon, "limit": 1, "appid": OWM_KEY},
        )
        resp.raise_for_status()
        results = resp.json()

    if not results:
        return None
    r = results[0]
    return {
        "name": r.get("name"),
        "state": r.get("state"),
        "country": r.get("country"),
        "lat": lat,
        "lon": lon,
    }
