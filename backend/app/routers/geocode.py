from fastapi import APIRouter, HTTPException, Query

from app.services import geocode_service

router = APIRouter()


@router.get("/search")
async def search(q: str = Query(..., min_length=2)):
    try:
        return {"results": await geocode_service.search_location(q)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"geocoding unavailable: {e}")


@router.get("/reverse")
async def reverse(lat: float = Query(...), lon: float = Query(...)):
    try:
        place = await geocode_service.reverse_geocode(lat, lon)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"geocoding unavailable: {e}")
    if not place:
        raise HTTPException(status_code=404, detail="no place found for these coordinates")
    return place
