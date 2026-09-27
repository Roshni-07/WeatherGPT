from fastapi import APIRouter, HTTPException, Query

from app.services import weather_service

router = APIRouter()


@router.get("/current")
async def current_weather(lat: float = Query(...), lon: float = Query(...)):
    try:
        current = await weather_service.get_current(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"weather provider unavailable: {e}")

    return {
        "theme": weather_service.map_condition_to_theme(current),
        **weather_service.summarize_for_prompt(current),
    }
