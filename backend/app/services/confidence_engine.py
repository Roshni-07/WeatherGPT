"""
Minimal confidence scoring for the live query pipeline. This is a starting
heuristic, not the full crowd-corroboration engine described in
docs/05_Backend_Schema_WeatherGPT.md -- that version (source agreement +
recency + crowd reports) comes once crowd_reports data actually exists.
"""


def score_single_source(weather_fetch_ok: bool, gemini_ok: bool, forecast_hours_ahead: int = 0) -> tuple[float, str]:
    if not weather_fetch_ok:
        return 0.2, "low"
    if not gemini_ok:
        return 0.4, "low"

    score = 0.95
    if forecast_hours_ahead > 24:
        score -= 0.15
    if forecast_hours_ahead > 72:
        score -= 0.2

    label = "high" if score >= 0.75 else "medium" if score >= 0.4 else "low"
    return round(score, 2), label
