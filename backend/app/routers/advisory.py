from fastapi import APIRouter, HTTPException

from app.services import advisory as A, snapshot

router = APIRouter()


@router.get("/personas")
def personas():
    return {"personas": [{"id": k, **{x: v[x] for x in ("name", "emoji", "tag")}} for k, v in A.PERSONAS.items()]}


@router.get("")
@router.get("/")
async def advisory(persona: str, lat: float, lon: float, name: str | None = None, am: int = 9, pm: int = 18, fav: str | None = None, heat: str | None = None):
    try:
        s = await snapshot.load(lat, lon, name, marine=(persona == "fisherman"), forecast_days=5)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Live weather is unreachable right now ({e}).")
    return A.build(persona, s, {"am": am, "pm": pm, "fav": fav or "", "heat": heat or "normal"})
