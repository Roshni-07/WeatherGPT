"""
Real weather data via OpenWeatherMap free tier (current weather + 5-day/3-hour
forecast). Requires OPENWEATHERMAP_API_KEY.

Docs: https://openweathermap.org/current, https://openweathermap.org/forecast5
"""
import os
import time
import httpx

OWM_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
BASE = "https://api.openweathermap.org/data/2.5"


async def get_current(lat: float, lon: float) -> dict:
    if not OWM_KEY:
        raise RuntimeError("OPENWEATHERMAP_API_KEY is not set")

    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            f"{BASE}/weather",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_forecast(lat: float, lon: float) -> dict:
    if not OWM_KEY:
        raise RuntimeError("OPENWEATHERMAP_API_KEY is not set")

    async with httpx.AsyncClient(timeout=6.0) as client:
        resp = await client.get(
            f"{BASE}/forecast",
            params={"lat": lat, "lon": lon, "appid": OWM_KEY, "units": "metric"},
        )
        resp.raise_for_status()
        return resp.json()


def map_condition_to_theme(current: dict) -> str:
    """
    Turns a real OWM 'current weather' payload into one of the four UI
    themes (clear-day / rain / storm / night) so the sky canvas reflects
    actual conditions instead of a hardcoded per-persona value.
    """
    weather_main = (current.get("weather", [{}])[0].get("main") or "").lower()
    dt = current.get("dt", int(time.time()))
    sunrise = current.get("sys", {}).get("sunrise", 0)
    sunset = current.get("sys", {}).get("sunset", 0)
    is_night = dt < sunrise or dt > sunset

    if weather_main in ("thunderstorm",):
        return "storm"
    if weather_main in ("rain", "drizzle"):
        return "rain"
    if is_night:
        return "night"
    return "clear-day"


def summarize_for_prompt(current: dict, forecast: dict | None = None) -> dict:
    """Flatten the raw OWM payload into the small set of fields the LLM
    prompt actually needs, so we're not stuffing the full API response
    into every request."""
    return {
        "condition": current.get("weather", [{}])[0].get("description"),
        "temp_c": current.get("main", {}).get("temp"),
        "feels_like_c": current.get("main", {}).get("feels_like"),
        "humidity_pct": current.get("main", {}).get("humidity"),
        "wind_speed_ms": current.get("wind", {}).get("speed"),
        "location_name": current.get("name"),
    }
