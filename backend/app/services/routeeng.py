"""Route weather: forecast at several points along the trip, timed to when you'll be there."""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from . import cities, engine as E, openmeteo as om
from .wxcodes import describe, is_thunder

log = logging.getLogger("weathergpt.route")
OSRM = "https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"


async def _geometry(a, b):
    """-> (coords[[lat,lon]], distance_km, duration_min, mode)"""
    if not om.is_mock():
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "WeatherGPT-SIH/1.0"}) as cl:
                r = await cl.get(OSRM.format(lon1=a[1], lat1=a[0], lon2=b[1], lat2=b[0]), params={"overview": "simplified", "geometries": "geojson"})
                j = r.json()
                rt = j["routes"][0]
                coords = [[y, x] for x, y in rt["geometry"]["coordinates"]]
                return coords, rt["distance"] / 1000, rt["duration"] / 60, "road"
        except Exception as e:  # noqa: BLE001
            log.info("OSRM unavailable, using straight line: %s", e)
    km = cities.haversine_km(a[0], a[1], b[0], b[1]) * 1.25  # rough road factor
    n = 12
    coords = [[a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n] for i in range(n + 1)]
    return coords, km, km / 45 * 60, "straight-line estimate"


def _sample(coords, k):
    cum = [0.0]
    for p, q in zip(coords, coords[1:]):
        cum.append(cum[-1] + cities.haversine_km(p[0], p[1], q[0], q[1]))
    total = cum[-1] or 1
    out = []
    for j in range(k):
        f = j / (k - 1)
        target = f * total
        idx = next((i for i, c in enumerate(cum) if c >= target), len(cum) - 1)
        out.append((f, coords[idx]))
    return out


def _thin(coords, n=120):
    step = max(1, len(coords) // n)
    return coords[::step] + ([coords[-1]] if coords[-1] not in coords[::step] else [])


def _stop_name(lat, lon, f, km, start_name, end_name):
    if f == 0:
        return start_name
    if f == 1:
        return end_name
    c, d = cities.nearest(lat, lon, 35)
    return f"near {c['name']}" if c else f"~{round(km * f)} km from start"


def _at(s, when):
    i = s.idx(when.date().isoformat(), when.hour)
    if i is None:
        i = s.i0
    return max(i, s.i0)


def _exposure(stops):
    return sum(x["mm"] * 2 + x["pop"] / 50 + (5 if x["thunder"] else 0) + (1 if x["gust"] >= 50 else 0) for x in stops)


async def plan(a, b, a_name, b_name, depart):
    coords, km, dur, mode = await _geometry(a, b)
    k = 3 if km < 30 else 4 if km < 120 else 5 if km < 300 else 6
    samples = _sample(coords, k)
    raws = await asyncio.gather(*[om.forecast(p[0], p[1], 0, 3) for _, p in samples])
    snaps = [E.Snap(r, None, None, {"name": "", "lat": p[0], "lon": p[1]}, "demo" if om.is_mock() else "live") for r, (_, p) in zip(raws, samples)]

    def stops_for(dep):
        res = []
        for (f, p), s in zip(samples, snaps):
            when = dep + timedelta(minutes=dur * f)
            i = _at(s, when)
            text, emoji = describe(s.code(i), s.is_day(i))
            res.append({"name": _stop_name(p[0], p[1], f, km, a_name, b_name), "lat": p[0], "lon": p[1], "time": E.hm12(when), "temp": round(s.temp(i)),
                        "pop": int(s.pop(i)), "mm": round(s.precip(i), 1), "gust": round(s.gust(i)), "wind": round(s.wind(i)), "emoji": emoji, "text": text,
                        "thunder": is_thunder(s.code(i)), "vis_km": round(s.vis(i) / 1000, 1), "issue": E.main_issue(s, i)})
        return res

    base = stops_for(depart)
    exp0 = _exposure(base)
    alts = []
    for shift in (-2, -1, 1, 2):
        dep = depart + timedelta(hours=shift)
        if dep < snaps[0].now_dt - timedelta(minutes=30):
            continue
        st = stops_for(dep)
        alts.append({"depart": E.hm12(dep), "shift_h": shift, "exposure": round(_exposure(st), 1), "rain_stops": sum(1 for x in st if x["mm"] >= 0.2 or x["pop"] >= 60)})
    best = min(alts, key=lambda x: x["exposure"], default=None)
    wet_stops = [x for x in base if x["mm"] >= 0.2 or x["pop"] >= 60]
    thunder = any(x["thunder"] for x in base)
    if thunder:
        level, head = "avoid", "Thunderstorm on your route"
    elif len(wet_stops) >= 2 or max(x["mm"] for x in base) >= 5:
        level, head = "caution", "Rain likely on part of your trip"
    elif wet_stops:
        level, head = "ok", "A brief wet patch is possible"
    else:
        level, head = "good", "Dry trip expected"
    if wet_stops:
        w = wet_stops[0]
        detail = f"Rain chance rises around {w['name']} at about {w['time']} ({w['pop']}%)."
    else:
        detail = "No rain expected at any point along the route."
    suggestion = ""
    if best and exp0 > 1.5 and best["exposure"] < exp0 * 0.6:
        suggestion = f"Leaving around {best['depart']} instead cuts your rain exposure noticeably."
    elif exp0 <= 1.5:
        suggestion = "Your planned departure time looks good."
    return {"from": a_name, "to": b_name, "distance_km": round(km), "duration_min": round(dur), "duration_text": f"{int(dur // 60)} h {int(dur % 60)} min" if dur >= 60 else f"{round(dur)} min",
            "depart": E.hm12(depart), "arrive": E.hm12(depart + timedelta(minutes=dur)), "mode": mode, "stops": base, "geometry": _thin(coords),
            "verdict": {"level": level, "headline": head, "detail": detail}, "suggestion": suggestion, "alternatives": alts,
            "best_depart": best["depart"] if best and suggestion.startswith("Leaving") else None,
            "source": "demo" if om.is_mock() else "live"}
