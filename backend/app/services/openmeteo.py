"""
Open-Meteo data layer (free, no API key; non-commercial use, attribution shown in UI).
 - forecast / current / air quality / marine / geocoding / climatology
 - in-memory TTL cache so many users don't hammer the API
 - WEATHERGPT_MOCK=1 swaps in synthetic data (offline demos) — always flagged as "demo"
"""
import asyncio
import logging
import os
import time
from datetime import date

import httpx

from . import mockdata

log = logging.getLogger("weathergpt.openmeteo")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARS = ",".join([
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation_probability",
    "precipitation", "weather_code", "cloud_cover", "visibility", "wind_speed_10m", "wind_direction_10m",
    "wind_gusts_10m", "uv_index", "is_day", "cape", "et0_fao_evapotranspiration", "soil_moisture_0_to_1cm",
])
CURRENT_VARS = ",".join([
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day", "precipitation", "weather_code",
    "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
])
DAILY_VARS = ",".join([
    "weather_code", "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "uv_index_max",
    "precipitation_sum", "precipitation_probability_max", "wind_gusts_10m_max",
])


def is_mock():
    return os.getenv("WEATHERGPT_MOCK", "") == "1"


_cache: dict = {}
_client: httpx.AsyncClient | None = None


def _http():
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(14.0, connect=6.0), headers={"User-Agent": "WeatherGPT-SIH/1.0"})
    return _client


async def _get(url, params, ttl):
    key = url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    hit = _cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    last = None
    for attempt in range(3):
        try:
            r = await _http().get(url, params=params)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"upstream {r.status_code}")
            data = r.json()
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(data.get("reason", "upstream error"))
            _cache[key] = (time.time() + ttl, data)
            if len(_cache) > 800:  # crude size cap
                for k in [k for k, v in _cache.items() if v[0] < time.time()][:200]:
                    _cache.pop(k, None)
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            await asyncio.sleep(0.4 * (attempt + 1))
    # serve slightly stale data rather than failing outright
    if hit:
        log.warning("serving stale cache for %s (%s)", url, last)
        return hit[1]
    raise RuntimeError(f"weather provider unreachable: {last}")


def _r(x):
    return round(float(x), 2)


async def forecast(lat, lon, past_days=1, forecast_days=7):
    if is_mock():
        return mockdata.forecast(lat, lon, past_days, forecast_days)
    return await _get(FORECAST_URL, {
        "latitude": _r(lat), "longitude": _r(lon), "timezone": "auto", "past_days": past_days,
        "forecast_days": forecast_days, "current": CURRENT_VARS, "hourly": HOURLY_VARS, "daily": DAILY_VARS,
        "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm",
    }, ttl=600)


async def air_quality(lat, lon):
    """Best effort: returns {'current': {...}} or None."""
    try:
        if is_mock():
            return mockdata.air(lat, lon)
        return await _get(AIR_URL, {
            "latitude": _r(lat), "longitude": _r(lon), "timezone": "auto",
            "current": "us_aqi,pm2_5,pm10", "hourly": "us_aqi", "forecast_days": 2,
        }, ttl=1200)
    except Exception as e:  # noqa: BLE001
        log.info("air quality unavailable: %s", e)
        return None


async def marine(lat, lon):
    """Wave data — only exists near the coast. Returns None for inland points."""
    try:
        if is_mock():
            return mockdata.marine(lat, lon)
        return await _get(MARINE_URL, {
            "latitude": _r(lat), "longitude": _r(lon), "timezone": "auto", "past_days": 1, "forecast_days": 5,
            "hourly": "wave_height,wave_period,swell_wave_height",
        }, ttl=1800)
    except Exception as e:  # noqa: BLE001
        log.info("marine unavailable: %s", e)
        return None


async def geocode(name, count=8, country="IN"):
    if is_mock():
        return []
    params = {"name": name, "count": count, "language": "en", "format": "json"}
    if country:
        params["countryCode"] = country
    data = await _get(GEOCODE_URL, params, ttl=86400)
    out = []
    for r in data.get("results", []) or []:
        out.append({
            "name": r.get("name"), "state": r.get("admin1"), "country": r.get("country_code"),
            "lat": r.get("latitude"), "lon": r.get("longitude"), "population": r.get("population"),
        })
    return out


async def climatology_tmax(lat, lon, month, day, tmax_today):
    """Average high for this calendar day over the last 10 years (+/-3 days). None if unavailable."""
    try:
        if is_mock():
            return mockdata.climate_tmax(lat, lon, tmax_today)
        y = date.today().year
        data = await _get(ARCHIVE_URL, {
            "latitude": _r(lat), "longitude": _r(lon), "timezone": "auto",
            "start_date": f"{y - 10}-01-01", "end_date": f"{y - 1}-12-31", "daily": "temperature_2m_max",
        }, ttl=86400)
        times = data["daily"]["time"]
        vals = data["daily"]["temperature_2m_max"]
        target = date(2001, month, day).timetuple().tm_yday
        picks = []
        for t, v in zip(times, vals):
            if v is None:
                continue
            yd = date(int(t[:4]), int(t[5:7]), int(t[8:10])).timetuple().tm_yday
            if abs(yd - target) <= 3 or abs(yd - target) >= 362:
                picks.append(v)
        if len(picks) < 20:
            return None
        mean = sum(picks) / len(picks)
        std = (sum((p - mean) ** 2 for p in picks) / len(picks)) ** 0.5
        return {"mean": round(mean, 1), "std": round(std, 1), "years": 10}
    except Exception as e:  # noqa: BLE001
        log.info("climatology unavailable: %s", e)
        return None


# ---------------------------------------------------------------- multi-location
LITE_HOURLY = "temperature_2m,apparent_temperature,precipitation,wind_gusts_10m,visibility,weather_code"
LITE_CURRENT = ("temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,"
                "cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m")
LITE_DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weather_code,sunrise,sunset"


async def _chunk_forecast(points):
    data = await _get(FORECAST_URL, {
        "latitude": ",".join(str(_r(p[0])) for p in points), "longitude": ",".join(str(_r(p[1])) for p in points),
        "timezone": "auto", "forecast_days": 3, "current": LITE_CURRENT, "hourly": LITE_HOURLY, "daily": LITE_DAILY,
    }, ttl=1200)
    return data if isinstance(data, list) else [data]


async def multi_forecast(points):
    """points: [(lat, lon), ...] -> list of forecast dicts in the same order."""
    if is_mock():
        return [mockdata.forecast(p[0], p[1], 0, 3) for p in points]
    chunks = [points[i:i + 20] for i in range(0, len(points), 20)]
    res = await asyncio.gather(*[_chunk_forecast(c) for c in chunks])
    return [x for part in res for x in part]


async def _chunk_air(points):
    data = await _get(AIR_URL, {
        "latitude": ",".join(str(_r(p[0])) for p in points), "longitude": ",".join(str(_r(p[1])) for p in points),
        "current": "us_aqi", "timezone": "auto",
    }, ttl=1800)
    return data if isinstance(data, list) else [data]


async def multi_air(points):
    try:
        if is_mock():
            return [mockdata.air(p[0], p[1]) for p in points]
        chunks = [points[i:i + 20] for i in range(0, len(points), 20)]
        res = await asyncio.gather(*[_chunk_air(c) for c in chunks])
        return [x for part in res for x in part]
    except Exception as e:  # noqa: BLE001
        log.info("multi air unavailable: %s", e)
        return [None] * len(points)
