import base64
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import engine as E, gemini_service as G, snapshot

router = APIRouter()


class SkyRequest(BaseModel):
    image_b64: str
    mime: str = "image/jpeg"
    lat: float
    lon: float
    name: str | None = None


@router.post("/analyze")
async def analyze(req: SkyRequest):
    if not G.available():
        raise HTTPException(503, "Sky photo analysis needs the Gemini key (GEMINI_API_KEY) to be set and working.")
    try:
        raw = base64.b64decode(req.image_b64.split(",")[-1])
        if len(raw) > 6_000_000:
            raise HTTPException(413, "Image too large — please use a smaller photo.")
        s = await snapshot.load(req.lat, req.lon, req.name, forecast_days=2)
        nb, _ = E.layman_now(s)
        ro = E.rain_outlook(s, s.i0, s.i0 + 6)
        facts = json.dumps({"place": s.name, "now": nb, "rain_next_6h_mm": ro["total"], "max_rain_chance_next_6h": ro["maxpop"]}, default=str)
        return {"analysis": G.analyze_sky(raw, req.mime, facts), "note": "A photo is one extra signal — it can't replace weather measurements.", "source": s.source}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Couldn't analyze the photo ({e}).")
