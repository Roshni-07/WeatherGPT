from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException

from app.services import mockdata, openmeteo as om, routeeng

router = APIRouter()


@router.get("")
@router.get("/")
async def route(from_lat: float, from_lon: float, to_lat: float, to_lon: float, from_name: str = "Start", to_name: str = "Destination", depart: str | None = None, day: int = 0):
    """depart = 'HH:MM' (24h). day = 0 today, 1 tomorrow."""
    base = mockdata.now_local() if om.is_mock() else datetime.now()
    try:
        hh, mm = (depart or f"{(base.hour + 1) % 24}:00").split(":")
        dep = base.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0) + timedelta(days=day)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "depart must look like 08:30")
    if dep < base - timedelta(minutes=30) and day == 0:
        dep += timedelta(days=1)
    try:
        return await routeeng.plan((from_lat, from_lon), (to_lat, to_lon), from_name, to_name, dep)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Couldn't plan this route right now ({e}).")
