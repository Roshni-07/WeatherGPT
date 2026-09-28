from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import chat_engine

router = APIRouter()


class QueryRequest(BaseModel):
    text: str
    user_id: str = "anon"
    language: str | None = "en"
    persona: str | None = "office"
    lat: float | None = None
    lon: float | None = None
    place_name: str | None = None
    profile: dict | None = None


@router.post("/")
async def handle_query(req: QueryRequest):
    lat, lon = (req.lat, req.lon) if req.lat is not None and req.lon is not None else (12.9716, 77.5946)
    try:
        return await chat_engine.respond(req.text, lat, lon, req.place_name, req.persona or "office", req.profile or {}, req.language or "en")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"I couldn't reach live weather data just now ({e}). Please try again in a moment.")
