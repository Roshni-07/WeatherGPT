from fastapi import APIRouter, HTTPException

from app.services import alerts_engine

router = APIRouter()


@router.get("/india")
async def india(lat: float | None = None, lon: float | None = None):
    """All-India alerts, ranked: places near the user first, then by severity."""
    try:
        return await alerts_engine.all_alerts(lat, lon)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Couldn't load alerts right now ({e}).")


@router.get("/active")
async def active(lat: float | None = None, lon: float | None = None):
    res = await india(lat, lon)
    return {"alerts": res["alerts"]}
