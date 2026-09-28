"""Plain-language helpers: WMO weather codes, rain/wind/UV/AQI wording."""

_WMO = {
    0: ("clear sky", "☀️", "🌙"), 1: ("mostly clear", "🌤️", "🌙"), 2: ("partly cloudy", "⛅", "☁️"),
    3: ("overcast", "☁️", "☁️"), 45: ("foggy", "🌫️", "🌫️"), 48: ("freezing fog", "🌫️", "🌫️"),
    51: ("light drizzle", "🌦️", "🌧️"), 53: ("drizzle", "🌦️", "🌧️"), 55: ("steady drizzle", "🌧️", "🌧️"),
    56: ("freezing drizzle", "🌧️", "🌧️"), 57: ("freezing drizzle", "🌧️", "🌧️"),
    61: ("light rain", "🌦️", "🌧️"), 63: ("rain", "🌧️", "🌧️"), 65: ("heavy rain", "🌧️", "🌧️"),
    66: ("freezing rain", "🌧️", "🌧️"), 67: ("freezing rain", "🌧️", "🌧️"),
    71: ("light snow", "🌨️", "🌨️"), 73: ("snow", "🌨️", "🌨️"), 75: ("heavy snow", "❄️", "❄️"),
    77: ("snow grains", "🌨️", "🌨️"), 80: ("light showers", "🌦️", "🌧️"), 81: ("showers", "🌧️", "🌧️"),
    82: ("violent showers", "⛈️", "⛈️"), 85: ("snow showers", "🌨️", "🌨️"), 86: ("heavy snow showers", "❄️", "❄️"),
    95: ("thunderstorm", "⛈️", "⛈️"), 96: ("thunderstorm with hail", "⛈️", "⛈️"),
    99: ("severe thunderstorm with hail", "⛈️", "⛈️"),
}


def describe(code, is_day=True):
    """-> (words, emoji)"""
    if code is None:
        return "conditions unavailable", "❔"
    text, day, night = _WMO.get(int(code), ("mixed conditions", "🌥️", "☁️"))
    return text, (day if is_day else night)


def is_thunder(code):
    return code is not None and int(code) >= 95


def is_wet_code(code):
    return code is not None and (51 <= int(code) <= 67 or 80 <= int(code) <= 82 or int(code) >= 95)


def rain_words(mm_per_hour):
    if mm_per_hour is None or mm_per_hour < 0.1:
        return "no rain"
    if mm_per_hour < 2.5:
        return "light rain"
    if mm_per_hour < 7.6:
        return "moderate rain"
    if mm_per_hour < 35:
        return "heavy rain"
    return "very heavy rain"


def wind_words(kmh):
    if kmh is None:
        return "wind data unavailable"
    if kmh < 6:
        return "almost calm"
    if kmh < 20:
        return "a light breeze"
    if kmh < 29:
        return "breezy"
    if kmh < 40:
        return "windy"
    if kmh < 62:
        return "very windy"
    return "storm-force winds"


def aqi_band(aqi):
    """US AQI scale (what the free air-quality API returns)."""
    if aqi is None:
        return None
    a = float(aqi)
    if a <= 50:
        return {"label": "Good", "tone": "good", "advice": "Air is clean — fine for outdoor plans."}
    if a <= 100:
        return {"label": "Moderate", "tone": "ok", "advice": "Fine for most people; very sensitive people may notice it."}
    if a <= 150:
        return {"label": "Poor for sensitive people", "tone": "caution", "advice": "Children, elders and people with asthma should go easy outdoors."}
    if a <= 200:
        return {"label": "Unhealthy", "tone": "warn", "advice": "Cut down long outdoor exercise; consider a mask outdoors."}
    if a <= 300:
        return {"label": "Very unhealthy", "tone": "warn", "advice": "Avoid outdoor exercise; keep windows closed."}
    return {"label": "Hazardous", "tone": "danger", "advice": "Stay indoors as much as possible."}


def uv_band(uv):
    if uv is None:
        return None
    u = float(uv)
    if u < 3:
        return "low"
    if u < 6:
        return "moderate"
    if u < 8:
        return "high"
    if u < 11:
        return "very high"
    return "extreme"


def feels_words(feels):
    if feels is None:
        return ""
    if feels >= 46:
        return "dangerously hot"
    if feels >= 41:
        return "very hot"
    if feels >= 35:
        return "hot and sticky"
    if feels >= 30:
        return "warm"
    if feels >= 22:
        return "comfortable"
    if feels >= 15:
        return "cool"
    if feels >= 8:
        return "cold"
    return "very cold"


def compass(deg):
    if deg is None:
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((float(deg) + 22.5) // 45) % 8]
