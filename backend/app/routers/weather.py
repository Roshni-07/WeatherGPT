import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.services import engine as E, openmeteo as om, snapshot
from app.services.wxcodes import describe, aqi_band

router = APIRouter()


def _profile(am, pm, fav, heat):
    return {"am": am, "pm": pm, "fav": fav or "", "heat": heat or "normal"}


@router.get("/briefing")
async def briefing(lat: float, lon: float, name: str | None = None, persona: str = "office", am: int = 9, pm: int = 18, fav: str | None = None, heat: str | None = None):
    """Everything the Chat/home briefing needs, in plain language."""
    try:
        s = await snapshot.load(lat, lon, name)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Live weather is unreachable right now ({e}). Please try again in a moment.")
    t = s.daily.get("temperature_2m_max", [None])
    di = s.daily_i(s.now_dt.date().isoformat())
    clim = None
    if di is not None and t[di] is not None:
        try:
            clim = await asyncio.wait_for(om.climatology_tmax(lat, lon, s.now_dt.month, s.now_dt.day, t[di]), timeout=5)
        except Exception:  # noqa: BLE001
            clim = None
    return E.briefing(s, _profile(am, pm, fav, heat), clim, persona)


@router.get("/pulse")
async def pulse(lat: float, lon: float, name: str | None = None, persona: str = "office", am: int = 9, pm: int = 18, fav: str | None = None, heat: str | None = None):
    """Lightweight refresh (sky + headline + chips) used every few minutes."""
    try:
        s = await snapshot.load(lat, lon, name, forecast_days=3)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    nb, _ = E.layman_now(s)
    head, kind = E.headline(s, nb)
    risks = E.compound_risks(s)
    return {"sky": E.sky_block(s), "headline": head, "headline_kind": kind, "now": nb, "updated": E.hm12(s.now_dt),
            "suggestions": E.suggestions(s, persona, _profile(am, pm, fav, heat), risks), "source": s.source, "place": s.name}


RANGES = {"24h": (1, 1), "3d": (1, 3), "7d": (1, 7)}


@router.get("/series")
async def series(lat: float, lon: float, name: str | None = None, range: str = "3d"):  # noqa: A002
    """Hourly real data for the Trends chart (last 24 h + forecast)."""
    try:
        s = await snapshot.load(lat, lon, name, past_days=1, forecast_days=RANGES.get(range, (1, 3))[1])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Live weather is unreachable right now ({e}).")
    n = s.n
    a = 0
    if range == "24h":  # 12 h back, 24 h ahead
        a = max(0, s.i0 - 12)
        b = min(n, s.i0 + 25)
    else:
        b = n
    idx = list(__builtins__['range'](a, b)) if isinstance(__builtins__, dict) else list(__builtins__.range(a, b))
    def col(f): return [None if f(i) is None else round(f(i), 1) for i in idx]
    days = []
    for i in idx:
        d = s.dt(i)
        days.append({"iso": s.t[i], "label": d.strftime("%a, %d %b"), "time": E.h12(d)})
    def hi_lo(vals):
        v = [x for x in vals if x is not None]
        return {"min": min(v), "max": max(v), "avg": round(sum(v) / len(v), 1)} if v else None
    temp, feels, hum, wind, gust = col(s.temp), col(s.feels), col(s.hum), col(s.wind), col(s.gust)
    pop, mm, uv, cloud = col(s.pop), col(s.precip), col(s.uv), col(s.cloud)
    codes = [describe(s.code(i), s.is_day(i)) for i in idx]
    return {
        "place": s.name, "source": s.source, "updated": E.hm12(s.now_dt), "now_index": idx.index(s.i0) if s.i0 in idx else 0, "range": range,
        "points": days, "temp": temp, "feels": feels, "humidity": hum, "wind": wind, "gust": gust, "pop": pop, "rain_mm": mm, "uv": uv, "cloud": cloud,
        "emoji": [c[1] for c in codes], "text": [c[0] for c in codes],
        "summary": {"temp": hi_lo(temp), "humidity": hi_lo(hum), "wind": hi_lo(wind), "rain_total": round(sum(x or 0 for x in mm), 1), "rain_peak_pop": max((x or 0) for x in pop)},
        "aqi": ({"value": round(s.aqi), **aqi_band(s.aqi)} if s.aqi is not None else None),
    }

