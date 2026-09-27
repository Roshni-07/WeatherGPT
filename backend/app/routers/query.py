from fastapi import APIRouter
from pydantic import BaseModel

from app.services import gemini_service, weather_service, geocode_service, confidence_engine

router = APIRouter()


class QueryRequest(BaseModel):
    text: str
    user_id: str
    language: str | None = "en"
    persona: str | None = "general"
    lat: float | None = None
    lon: float | None = None


class QueryResponse(BaseModel):
    answer: str
    confidence: str
    language: str
    theme: str
    location_name: str | None = None


@router.post("/", response_model=QueryResponse)
async def handle_query(req: QueryRequest):
    weather_ok = False
    gemini_ok = False
    theme = "clear-day"
    location_name = None

    # 1. Understand the query
    try:
        intent = gemini_service.extract_intent(req.text, req.persona or "general")
        gemini_ok = True
    except Exception:
        # Gemini down or misconfigured -- fall back to a neutral intent
        # instead of a single canned string everywhere downstream.
        intent = {
            "location": "unspecified",
            "time_window": "unspecified",
            "parameter": "general",
            "persona_context": req.persona or "general",
        }

    # 2. Resolve a location: prefer lat/lon from the browser, else geocode
    #    whatever the LLM extracted from the text.
    lat, lon = req.lat, req.lon
    try:
        if lat is None or lon is None:
            if intent["location"] != "unspecified":
                candidates = await geocode_service.search_location(intent["location"], limit=1)
                if candidates:
                    lat, lon = candidates[0]["lat"], candidates[0]["lon"]
                    location_name = candidates[0]["name"]
        else:
            place = await geocode_service.reverse_geocode(lat, lon)
            location_name = place["name"] if place else None
    except Exception:
        pass  # geocoding is best-effort; weather fetch below handles no-location gracefully

    # 3. Fetch real weather for that location
    weather_summary = {}
    if lat is not None and lon is not None:
        try:
            current = await weather_service.get_current(lat, lon)
            weather_ok = True
            theme = weather_service.map_condition_to_theme(current)
            weather_summary = weather_service.summarize_for_prompt(current)
            location_name = location_name or weather_summary.get("location_name")
        except Exception:
            weather_ok = False

    # 4. Confidence
    forecast_hours_ahead = {
        "now": 0, "today": 6, "tomorrow": 24, "this_week": 96,
        "historical": 0, "unspecified": 0,
    }.get(intent["time_window"], 0)
    score, confidence_label = confidence_engine.score_single_source(weather_ok, gemini_ok, forecast_hours_ahead)

    # 5. Compose the final answer
    if gemini_ok and weather_ok:
        try:
            answer = gemini_service.compose_response(intent, weather_summary, confidence_label, req.language or "en")
        except Exception:
            answer = _fallback_answer(weather_summary, confidence_label)
    elif weather_ok:
        answer = _fallback_answer(weather_summary, confidence_label)
    else:
        answer = (
            "I couldn't reach live weather data just now"
            + (f" for {location_name}" if location_name else "")
            + ". Please check your location and try again in a moment."
        )

    return QueryResponse(
        answer=answer,
        confidence=confidence_label,
        language=req.language or "en",
        theme=theme,
        location_name=location_name,
    )


def _fallback_answer(weather_summary: dict, confidence_label: str) -> str:
    """Used when Gemini is unavailable but real weather data was fetched
    successfully -- still varies with the actual data, unlike a single
    hardcoded string."""
    condition = weather_summary.get("condition", "conditions are unclear")
    temp = weather_summary.get("temp_c")
    wind = weather_summary.get("wind_speed_ms")
    place = weather_summary.get("location_name", "your location")

    parts = [f"Current conditions in {place}: {condition}"]
    if temp is not None:
        parts.append(f"{temp}\u00b0C")
    if wind is not None:
        parts.append(f"wind {wind} m/s")
    return ", ".join(parts) + f". (confidence: {confidence_label}, AI summary unavailable right now)"
