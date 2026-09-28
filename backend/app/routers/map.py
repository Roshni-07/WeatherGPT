import os

import httpx
from fastapi import APIRouter, HTTPException, Response

from app.services import alerts_engine

router = APIRouter()
OWM_LAYERS = {"temp": "temp_new", "wind": "wind_new", "clouds": "clouds_new", "rain": "precipitation_new", "pressure": "pressure_new"}


@router.get("/points")
async def points():
    try:
        return {"points": await alerts_engine.map_points()}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Couldn't load map data right now ({e}).")


@router.get("/config")
def config():
    return {"owm_tiles": bool(os.getenv("OPENWEATHERMAP_API_KEY")), "layers": list(OWM_LAYERS)}


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
async def tiles(layer: str, z: int, x: int, y: int):
    """Proxies OpenWeatherMap weather-map tiles so the API key never reaches the browser."""
    key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not key or layer not in OWM_LAYERS:
        raise HTTPException(404, "tile layer unavailable")
    async with httpx.AsyncClient(timeout=8.0) as cl:
        r = await cl.get(f"https://tile.openweathermap.org/map/{OWM_LAYERS[layer]}/{z}/{x}/{y}.png", params={"appid": key})
    if r.status_code != 200:
        raise HTTPException(404, "tile not available")
    return Response(content=r.content, media_type="image/png", headers={"Cache-Control": "public, max-age=600"})
