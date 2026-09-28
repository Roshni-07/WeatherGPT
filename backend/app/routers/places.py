from fastapi import APIRouter, Query

from app.services import cities, openmeteo as om

router = APIRouter()


@router.get("/suggest")
async def suggest(q: str = Query("", max_length=60), limit: int = 10):
    """A–Z suggestions from the first keystroke: built-in Indian cities instantly,
    plus live geocoding (any town/village) once 3+ letters are typed."""
    q = q.strip()
    local = cities.prefix_search(q, 14)
    results = [{"name": c["name"], "state": c["state"], "lat": c["lat"], "lon": c["lon"], "coastal": c["coastal"], "kind": "city"} for c in local]
    if len(q) >= 3:
        try:
            for g in await om.geocode(q, count=8):
                if g["lat"] is None:
                    continue
                if any(abs(r["lat"] - g["lat"]) < 0.25 and abs(r["lon"] - g["lon"]) < 0.25 for r in results):
                    continue
                results.append({"name": g["name"], "state": g.get("state") or "", "lat": g["lat"], "lon": g["lon"], "coastal": False, "kind": "place"})
        except Exception:  # noqa: BLE001
            pass  # geocoder down -> built-in list still works
    ql = q.lower()
    results.sort(key=lambda r: (0 if r["name"].lower().startswith(ql) else 1, r["name"].lower()))
    return {"results": results[:limit], "query": q}


@router.get("/reverse")
async def reverse(lat: float, lon: float):
    c, d = cities.nearest(lat, lon, 40)
    if c:
        return {"name": c["name"].split(" (")[0], "state": c["state"], "lat": lat, "lon": lon, "distance_km": round(d)}
    return {"name": "Your location", "state": "", "lat": lat, "lon": lon, "distance_km": None}


@router.get("/all")
def all_places():
    """The whole built-in A–Z list (~130 rows) so the browser can filter instantly, letter by letter."""
    return {"results": [{"name": c["name"], "state": c["state"], "lat": c["lat"], "lon": c["lon"], "coastal": c["coastal"], "kind": "city"} for c in cities.CITIES]}
