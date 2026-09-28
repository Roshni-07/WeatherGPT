"""
India-wide alerts.

1. DERIVED alerts — scanned from forecast-model data for ~40 cities using IMD-style
   thresholds (24 h rain, very hot days, gusts, fog, air quality, thunder).
   Labelled "forecast-based" — they are NOT official warnings.
2. OFFICIAL alerts — NDMA SACHET public CAP/RSS feed, fetched best-effort.
   If the feed can't be reached the app says so instead of pretending.

Alerts are then ranked: places near the user first, then the rest of India,
each group by severity.
"""
import asyncio
import email.utils
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import httpx

from . import cities, openmeteo as om
from .wxcodes import aqi_band, describe, compass

log = logging.getLogger("weathergpt.alerts")
FMT = "%Y-%m-%dT%H:%M"
COLORS = {1: "yellow", 2: "orange", 3: "red"}
SACHET_FEEDS = [
    "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml",
    "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=rss",
]

_snap = {"exp": 0, "data": None}
_official = {"exp": 0, "data": None, "status": "off"}


async def india_snapshot():
    """Current + next-48h data for every scan city (cached 20 min)."""
    if _snap["data"] and _snap["exp"] > time.time():
        return _snap["data"]
    pts = [(c["lat"], c["lon"]) for c in cities.SCAN_CITIES]
    fc, aq = await asyncio.gather(om.multi_forecast(pts), om.multi_air(pts))
    data = []
    for c, f, a in zip(cities.SCAN_CITIES, fc, aq):
        data.append({"city": c, "raw": f, "aqi": (a or {}).get("current", {}).get("us_aqi") if a else None})
    _snap.update(exp=time.time() + 1200, data=data)
    return data


def _win(raw, hours=24):
    h = raw["hourly"]
    ct = (raw.get("current") or {}).get("time") or h["time"][0]
    i0 = next((i for i, t in enumerate(h["time"]) if t[:13] == ct[:13]), 0)
    return h, i0, min(len(h["time"]), i0 + hours)


def _lab(t):
    d = datetime.strptime(t, FMT)
    return f"{d.hour % 12 or 12} {'AM' if d.hour < 12 else 'PM'}"


def _daylab(d, today):
    return "today" if d == today else "tomorrow" if (d - today).days == 1 else d.strftime("%a")


def _when(h, a, b):
    da = datetime.strptime(h["time"][a], FMT)
    db = datetime.strptime(h["time"][min(b, len(h["time"]) - 1)], FMT)
    today = datetime.strptime(h["time"][0], FMT).date()
    start = f"{_daylab(da.date(), today)} {_lab(h['time'][a])}"
    end = _lab(h["time"][min(b, len(h["time"]) - 1)])
    if db.date() != da.date():
        end = f"{_daylab(db.date(), today)} {end}"
    return f"{start} – {end}"


def _cluster(idx, precip):
    """Group wet hours (gaps <= 2h) and return the wettest cluster as (first, last)."""
    groups, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > 3:
            groups.append(cur)
            cur = []
        cur.append(i)
    if cur:
        groups.append(cur)
    best = max(groups, key=lambda g: sum(precip(i) for i in g))
    return best[0], best[-1]


def derive(snapshot):
    out = []
    for item in snapshot:
        c, raw = item["city"], item["raw"]
        try:
            h, a, b24 = _win(raw, 24)
            _, _, b48 = _win(raw, 48)
        except Exception:  # noqa: BLE001
            continue
        P = lambda k, i: (h.get(k) or [None] * (i + 1))[i] or 0  # noqa: E731
        rain24 = sum(P("precipitation", i) for i in range(a, b24))
        rain48 = sum(P("precipitation", i) for i in range(a, b48))
        peak = max((P("precipitation", i) for i in range(a, b24)), default=0)
        wet = [i for i in range(a, b24) if P("precipitation", i) >= 0.5]
        gust = max((P("wind_gusts_10m", i) for i in range(a, b24)), default=0)
        tmax = max((P("temperature_2m", i) for i in range(a, b24)), default=0)
        fmax = max((P("apparent_temperature", i) for i in range(a, b24)), default=0)
        tmin = min((P("temperature_2m", i) for i in range(a, b24)), default=99)
        vmin = min(((h.get("visibility") or [30000] * (i + 1))[i] or 30000 for i in range(a, b24)), default=30000)
        thunder = [i for i in range(a, b24) if int(P("weather_code", i)) >= 95]

        def add(kind, sev, title, what, why, do, i_from, i_to, metric):
            out.append({
                "id": f"{kind}-{c['name']}", "type": kind, "severity": sev, "color": COLORS[sev], "title": title,
                "place": c["name"], "state": c["state"], "lat": c["lat"], "lon": c["lon"], "what": what, "why": why, "do": do,
                "when": _when(h, i_from, i_to), "metric": metric, "source": "forecast", "source_label": "Forecast-model based",
            })

        # --- rain
        if rain24 >= 35 or peak >= 40:
            sev = 3 if (rain24 >= 115.6 or peak >= 40) else 2 if rain24 >= 64.5 else 1
            label = {1: "Moderate to heavy rain", 2: "Heavy rain", 3: "Very heavy rain"}[sev]
            i_from, i_to = ((lambda c: (c[0], c[1] + 1))(_cluster(wet, lambda i: P('precipitation', i))) if wet else (a, b24))
            add("rain", sev, f"{label} likely in {c['name']}", f"About {round(rain24)} mm of rain expected in the next 24 hours (up to {round(peak, 1)} mm in a single hour).",
                "Rain like this can waterlog roads and underpasses, slow traffic and cause local flooding.",
                ["Avoid low-lying roads and underpasses", "Postpone non-urgent travel during the heaviest hours", "Keep phones charged and move vehicles to higher ground if water rises"],
                i_from, i_to, f"{round(rain24)} mm / 24 h")
        # --- flood-prone (multi-day)
        if rain48 >= 120 and not (rain24 >= 115.6):
            sev = 3 if rain48 >= 200 else 2
            add("flood", sev, f"Flood risk building in {c['name']} area", f"Roughly {round(rain48)} mm of rain forecast over 48 hours.",
                "Ground and drains can saturate after long spells of rain, raising flood risk in low areas.",
                ["Stay updated with local authority notices", "Avoid river banks and low crossings", "Prepare an emergency bag if you live in a flood-prone area"], a, b48, f"{round(rain48)} mm / 48 h")
        # --- heat
        if tmax >= 40 and not c["hill"]:
            sev = 3 if tmax >= 46 else 2 if tmax >= 43 else 1
            hot = [i for i in range(a, b24) if P("temperature_2m", i) >= 40]
            add("heat", sev, f"{'Extreme' if sev == 3 else 'Very'} hot day in {c['name']}", f"Temperature may reach {round(tmax)}°C (feels like {round(fmax)}°C).",
                "Extreme heat can cause heat exhaustion and heat stroke, especially for elders, kids and outdoor workers.",
                ["Stay indoors between 12 and 4 PM if you can", "Drink water often; use ORS if you sweat a lot", "Never leave children or pets in parked vehicles"],
                hot[0] if hot else a, (hot[-1] + 1) if hot else b24, f"{round(tmax)}°C")
        # --- cold
        if tmin <= 4 and not c["hill"]:
            sev = 2 if tmin <= 2 else 1
            add("cold", sev, f"Cold wave conditions in {c['name']}", f"Temperature may fall to {round(tmin)}°C.", "Cold air is hard on elders, babies and people sleeping outdoors.",
                ["Layer up, cover head and hands", "Keep elders warm indoors"], a, b24, f"{round(tmin)}°C")
        # --- thunder
        if thunder:
            sev = 2 if gust >= 60 else 1
            add("storm", sev, f"Thunderstorms likely in {c['name']}", "Thunder and lightning are forecast" + (f", with gusts up to {round(gust)} km/h." if gust >= 40 else "."),
                "Lightning is the biggest danger outdoors, and storms can bring sudden gusty winds.",
                ["Stay indoors during thunder; avoid trees, poles and open fields", "Unplug sensitive electronics"], thunder[0], thunder[-1] + 1, "Thunderstorm")
        # --- wind
        if gust >= 60 and not thunder:
            sev = 3 if gust >= 90 else 2 if gust >= 75 else 1
            g = [i for i in range(a, b24) if P("wind_gusts_10m", i) >= 60]
            add("wind", sev, f"Strong winds in {c['name']}", f"Gusts up to {round(gust)} km/h ({compass(None) or 'strong'} winds).",
                "Strong gusts can bring down branches and hoardings and make riding unsafe.",
                ["Secure loose items on balconies and roofs", "Avoid parking under trees or hoardings", "Two-wheeler riders: consider postponing"], g[0], g[-1] + 1, f"{round(gust)} km/h gusts")
        # --- fog
        if vmin < 500:
            sev = 2 if vmin < 200 else 1
            f_ = [i for i in range(a, b24) if ((h.get("visibility") or [30000] * (i + 1))[i] or 30000) < 500]
            add("fog", sev, f"{'Dense fog' if sev == 2 else 'Fog'} in {c['name']}", f"Visibility may drop to about {round(vmin)} m.", "Fog hides vehicles and hazards and delays trains and flights.",
                ["Drive slowly with low-beam headlights", "Allow extra travel time; check train/flight status"], f_[0], f_[-1] + 1, f"{round(vmin)} m visibility")
        # --- air
        aq = item.get("aqi")
        if aq is not None and aq >= 151:
            sev = 3 if aq >= 301 else 2 if aq >= 201 else 1
            band = aqi_band(aq)
            add("air", sev, f"{band['label']} air in {c['name']}", f"US AQI is about {round(aq)}.", "Fine dust can irritate lungs — kids, elders and people with asthma feel it first.",
                [band["advice"], "Keep windows closed and use a mask outdoors"], a, b24, f"AQI {round(aq)}")
    return out


def _clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


async def official():
    """NDMA SACHET RSS, best-effort. Returns (alerts, status)."""
    if om.is_mock():
        return [], "off"
    if _official["exp"] > time.time():
        return _official["data"], _official["status"]
    alerts, status = [], "unreachable"
    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers={"User-Agent": "WeatherGPT-SIH/1.0"}) as cl:
        for url in SACHET_FEEDS:
            try:
                r = await cl.get(url)
                if r.status_code != 200 or b"<" not in r.content[:20]:
                    continue
                root = ET.fromstring(r.content)
                for it in root.iter("item"):
                    title = (it.findtext("title") or "").strip()
                    desc = _clean(it.findtext("description"))
                    link = (it.findtext("link") or "").strip()
                    pub = it.findtext("pubDate")
                    try:
                        pdt = email.utils.parsedate_to_datetime(pub) if pub else None
                        if pdt and (datetime.now(pdt.tzinfo) - pdt) > timedelta(days=3):
                            continue
                    except Exception:  # noqa: BLE001
                        pdt = None
                    blob = f"{title} {desc}".lower()
                    sev = 3 if re.search(r"\bred\b|extreme|very severe|cyclone", blob) else 2 if re.search(r"orange|severe|heavy|warning", blob) else 1
                    state = next((s for s in cities.STATES if s.lower() in blob), None)
                    c = next((x for x in cities.SCAN_CITIES if x["state"] == state), None) or next((x for x in cities.CITIES if x["state"] == state), None)
                    kind = "rain" if re.search(r"rain|flood|cloudburst", blob) else "heat" if re.search(r"heat", blob) else "storm" if re.search(r"thunder|lightning|cyclone", blob) else \
                        "wind" if "wind" in blob else "fog" if "fog" in blob else "cold" if re.search(r"cold", blob) else "alert"
                    alerts.append({
                        "id": "ndma-" + str(abs(hash(title + link)) % 10**8), "type": kind, "severity": sev, "color": COLORS[sev], "title": title[:140] or "Official alert",
                        "place": state or "India", "state": state or "", "lat": c["lat"] if c else None, "lon": c["lon"] if c else None,
                        "what": desc[:320], "why": "Issued by an official Indian agency via NDMA SACHET.", "do": ["Follow instructions from local authorities", "Check the SACHET app or website for full details"],
                        "when": pdt.strftime("%d %b, %I:%M %p").lstrip("0") if pdt else "recent", "metric": "Official", "source": "ndma", "source_label": "Official · NDMA SACHET", "link": link,
                    })
                status = "ok"
                break
            except Exception as e:  # noqa: BLE001
                log.info("sachet fetch failed %s: %s", url, e)
    _official.update(exp=time.time() + 600, data=alerts, status=status)
    return alerts, status


def rank(alerts, lat=None, lon=None, near_km=250):
    for a in alerts:
        if lat is not None and a.get("lat") is not None:
            a["distance_km"] = round(cities.haversine_km(lat, lon, a["lat"], a["lon"]))
            a["near"] = a["distance_km"] <= near_km
        else:
            a["distance_km"], a["near"] = None, False
    # official alerts first within the same severity, then nearest
    alerts.sort(key=lambda a: (not a["near"], -a["severity"], a["source"] != "ndma", a["distance_km"] if a["distance_km"] is not None else 9999))
    return alerts


async def all_alerts(lat=None, lon=None):
    snap = await india_snapshot()
    derived = derive(snap)
    off, status = await official()
    ranked = rank(off + derived, lat, lon)
    return {
        "alerts": ranked, "near_count": sum(1 for a in ranked if a["near"]), "total": len(ranked),
        "by_severity": {k: sum(1 for a in ranked if a["severity"] == v) for k, v in (("yellow", 1), ("orange", 2), ("red", 3))},
        "updated": datetime.now().strftime("%I:%M %p").lstrip("0"), "source": "demo" if om.is_mock() else "live",
        "official_feed": status,
        "note": "Forecast-based alerts are automatic and not official warnings. For official warnings see IMD (mausam.imd.gov.in) and NDMA SACHET.",
    }


async def map_points():
    snap = await india_snapshot()
    out = []
    for item in snap:
        c, raw = item["city"], item["raw"]
        cur = raw.get("current") or {}
        d = raw.get("daily") or {}
        code = cur.get("weather_code")
        text, emoji = describe(code, bool(cur.get("is_day", 1)))
        out.append({
            "name": c["name"], "state": c["state"], "lat": c["lat"], "lon": c["lon"], "temp": round(cur.get("temperature_2m", 0)),
            "feels": round(cur.get("apparent_temperature", cur.get("temperature_2m", 0))), "humidity": round(cur.get("relative_humidity_2m", 0)),
            "wind": round(cur.get("wind_speed_10m", 0)), "gust": round(cur.get("wind_gusts_10m", 0)), "wind_deg": cur.get("wind_direction_10m"),
            "wind_dir": compass(cur.get("wind_direction_10m")), "cloud": round(cur.get("cloud_cover", 0) or 0), "rain": round(cur.get("precipitation", 0) or 0, 1), "code": code, "text": text, "emoji": emoji,
            "hi": round((d.get("temperature_2m_max") or [0])[0] or 0), "lo": round((d.get("temperature_2m_min") or [0])[0] or 0),
            "rain_today": round((d.get("precipitation_sum") or [0])[0] or 0, 1), "pop": (d.get("precipitation_probability_max") or [None])[0],
            "aqi": round(item["aqi"]) if item["aqi"] is not None else None, "time": cur.get("time"),
        })
    return out
