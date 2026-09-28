"""
WeatherGPT decision engine (deterministic — no LLM in the numbers path).

    RAW DATA  ->  Snap (clean hourly view)  ->  scoring / windows / risks / plan
              ->  plain-language, actionable output

Every sentence shown to a user is built here from real forecast values, so the
app can't "hallucinate" weather. An LLM (if configured) is only used elsewhere
for free-form questions, translation and sky photos.
"""
from datetime import datetime, timedelta

from .wxcodes import (aqi_band, compass, describe, feels_words, is_thunder, rain_words, uv_band, wind_words)

FMT = "%Y-%m-%dT%H:%M"


def h12(dt):
    """'4 PM' — avoids %-I which breaks on Windows."""
    return f"{dt.hour % 12 or 12} {'AM' if dt.hour < 12 else 'PM'}"


def hm12(dt):
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


# ------------------------------------------------------------------ Snap
class Snap:
    def __init__(self, raw, aqi_raw=None, marine_raw=None, place=None, source="live"):
        self.raw = raw
        self.h = raw["hourly"]
        self.t = self.h["time"]
        self.n = len(self.t)
        self.cur = raw.get("current") or {}
        self.daily = raw.get("daily") or {}
        self.place = place or {}
        self.source = source
        self._dt = [datetime.strptime(x, FMT) for x in self.t]
        ct = self.cur.get("time") or self.t[0]
        key = ct[:13]
        self.i0 = next((i for i, x in enumerate(self.t) if x[:13] == key), 0)
        self.now_dt = datetime.strptime(ct, FMT) if ct else self._dt[self.i0]
        self.aqi = None
        self.pm25 = None
        if aqi_raw and (aqi_raw.get("current") or {}).get("us_aqi") is not None:
            self.aqi = float(aqi_raw["current"]["us_aqi"])
            self.pm25 = aqi_raw["current"].get("pm2_5")
        self.marine = marine_raw

    # -- raw accessors (None-safe)
    def a(self, name, i, default=None):
        arr = self.h.get(name)
        if arr is None or i < 0 or i >= len(arr):
            return default
        v = arr[i]
        return default if v is None else v

    def temp(self, i): return float(self.a("temperature_2m", i, 25))
    def feels(self, i): return float(self.a("apparent_temperature", i, self.temp(i)))
    def hum(self, i): return float(self.a("relative_humidity_2m", i, 60))
    def precip(self, i): return float(self.a("precipitation", i, 0))
    def code(self, i): return self.a("weather_code", i, 0)
    def cloud(self, i): return float(self.a("cloud_cover", i, 30))
    def vis(self, i): return float(self.a("visibility", i, 20000))
    def wind(self, i): return float(self.a("wind_speed_10m", i, 8))
    def gust(self, i): return float(self.a("wind_gusts_10m", i, self.wind(i) * 1.4))
    def uv(self, i): return float(self.a("uv_index", i, 0))
    def is_day(self, i): return bool(self.a("is_day", i, 1))
    def cape(self, i): return float(self.a("cape", i, 0))
    def et0(self, i): return float(self.a("et0_fao_evapotranspiration", i, 0))
    def soil(self, i): return self.a("soil_moisture_0_to_1cm", i, None)

    def pop(self, i):
        v = self.a("precipitation_probability", i)
        if v is not None:
            return float(v)
        mm = self.precip(i)
        return 85.0 if mm >= 1 else 55.0 if mm >= 0.2 else 6.0

    def wet(self, i):
        return self.precip(i) >= 0.2 or self.pop(i) >= 60 or is_thunder(self.code(i))

    def dt(self, i): return self._dt[max(0, min(i, self.n - 1))]
    def label(self, i): return h12(self.dt(i))

    def day_name(self, i):
        d = self.dt(i).date()
        today = self.now_dt.date()
        diff = (d - today).days
        return "Today" if diff == 0 else "Tomorrow" if diff == 1 else "Yesterday" if diff == -1 else d.strftime("%a")

    def idx(self, date_str, hour):
        key = f"{date_str}T{hour:02d}"
        return next((i for i, x in enumerate(self.t) if x[:13] == key), None)

    def day_range(self, day_offset, h_from=0, h_to=24):
        date_str = (self.now_dt.date() + timedelta(days=day_offset)).isoformat()
        a = self.idx(date_str, h_from) if h_from < 24 else None
        b = self.idx(date_str, h_to) if h_to < 24 else None
        if a is None:
            a = next((i for i, x in enumerate(self.t) if x[:10] == date_str), None)
        if a is None:
            return None
        if b is None:
            b = max((i for i, x in enumerate(self.t) if x[:10] == date_str), default=a) + 1
        return a, b

    def daily_i(self, date_str):
        try:
            return self.daily["time"].index(date_str)
        except (KeyError, ValueError):
            return None

    def sun(self, date_str):
        di = self.daily_i(date_str)
        if di is None:
            return None, None
        try:
            return (datetime.strptime(self.daily["sunrise"][di], FMT), datetime.strptime(self.daily["sunset"][di], FMT))
        except Exception:  # noqa: BLE001
            return None, None

    def conf(self, i):
        hrs = i - self.i0
        return "high" if hrs <= 12 else "medium" if hrs <= 48 else "low"

    @property
    def name(self):
        return self.place.get("name") or "your location"


# ------------------------------------------------------------------ scoring
ACT = {
    "outdoor": dict(label="outdoor plans", ideal=(18, 30), hot=34, wind=25, gust=40, day=True, vis=2000, uv=True, aqi=True),
    "cycling": dict(label="a cycle ride", ideal=(16, 27), hot=31, wind=20, gust=35, day=True, vis=3000, uv=True, aqi=True, feels_hot=33),
    "running": dict(label="a run", ideal=(12, 25), hot=29, wind=25, gust=40, day=True, vis=2000, uv=True, aqi=True, feels_hot=32),
    "walking": dict(label="a walk", ideal=(16, 29), hot=33, wind=28, gust=45, day=True, vis=1500, uv=True, aqi=True),
    "riding": dict(label="a bike or scooter ride", ideal=(14, 34), hot=38, wind=30, gust=40, day=False, vis=1500, uv=False, aqi=False),
    "commute": dict(label="your commute", ideal=(14, 36), hot=39, wind=35, gust=50, day=False, vis=1000, uv=False, aqi=False),
    "picnic": dict(label="a picnic", ideal=(20, 30), hot=33, wind=22, gust=35, day=True, vis=2000, uv=True, aqi=True),
    "kids": dict(label="outdoor play", ideal=(18, 30), hot=33, wind=28, gust=40, day=True, vis=1500, uv=True, aqi=True),
    "field": dict(label="field work", ideal=(16, 34), hot=37, wind=35, gust=55, day=True, vis=500, uv=False, aqi=False),
}
SPECIAL = {"laundry": "drying clothes outside", "spray": "spraying crops", "photo": "photography",
           "stargaze": "stargazing", "flying": "flying"}


def act_label(act):
    return ACT.get(act, {}).get("label") or SPECIAL.get(act, act)


def score_hour(act, s, i):
    if act in SPECIAL:
        return _score_special(act, s, i)
    p = ACT.get(act, ACT["outdoor"])
    temp, feels, pop, mm = s.temp(i), s.feels(i), s.pop(i), s.precip(i)
    wind, gust, vis, uv = s.wind(i), s.gust(i), s.vis(i), s.uv(i)
    score = 100.0
    if is_thunder(s.code(i)):
        score -= 70
    if mm >= 0.2:
        score -= min(60, 30 + mm * 8)
    elif pop >= 30:
        score -= (pop - 20) * 0.45
    lo, hi = p["ideal"]
    if temp < lo:
        score -= (lo - temp) * 2.5
    if temp > hi:
        score -= (temp - hi) * 3.0
    fh = p.get("feels_hot")
    if fh and feels > fh:
        score -= (feels - fh) * 3
    if feels >= 41:
        score -= 25
    if wind > p["wind"]:
        score -= (wind - p["wind"]) * 1.5
    if gust > p["gust"]:
        score -= (gust - p["gust"]) * 1.0
    if vis < p["vis"]:
        score -= 25
    if p["day"] and not s.is_day(i):
        score -= 30
    if p["uv"]:
        score -= 18 if uv >= 8 else 8 if uv >= 6 else 0
    if p["aqi"] and s.aqi and (i - s.i0) <= 12 and s.aqi > 100:
        score -= min(30, (s.aqi - 100) * 0.25)
    return max(0.0, min(100.0, score))


def _score_special(act, s, i):
    temp, pop, mm, hum = s.temp(i), s.pop(i), s.precip(i), s.hum(i)
    wind, gust, cloud, vis = s.wind(i), s.gust(i), s.cloud(i), s.vis(i)
    day = s.is_day(i)
    score = 100.0
    if act == "laundry":
        if not day:
            score -= 60
        if mm >= 0.1:
            score -= 70
        elif pop >= 30:
            score -= (pop - 20) * 0.6
        if hum > 75:
            score -= (hum - 75) * 1.8
        if cloud > 80:
            score -= 12
        if wind < 3:
            score -= 10
        if temp < 22:
            score -= 10
    elif act == "spray":
        if wind > 15:
            score -= (wind - 15) * 4
        if gust > 25:
            score -= (gust - 25) * 2
        if any(s.wet(j) for j in range(i, min(i + 6, s.n))):
            score -= 50
        if temp > 32:
            score -= (temp - 32) * 4
        if not day:
            score -= 20
        if hum < 40:
            score -= 10
    elif act == "photo":
        sr, ss = s.sun(s.t[i][:10])
        dt = s.dt(i)
        golden = False
        if sr and ss:
            golden = (sr - timedelta(minutes=30) <= dt <= sr + timedelta(hours=1)) or (ss - timedelta(hours=1) <= dt <= ss + timedelta(minutes=30))
        score = 100 if golden else (65 if day else 25)
        if cloud < 15:
            score -= 8
        elif 25 <= cloud <= 75:
            score += 0
        elif cloud > 90:
            score -= 20
        if mm >= 0.1:
            score -= 60
        elif pop >= 40:
            score -= 20
        if vis < 3000:
            score -= 20
    elif act == "stargaze":
        if day:
            return 3.0
        if cloud > 20:
            score -= (cloud - 20) * 1.1
        if mm >= 0.1:
            score -= 80
        elif pop >= 40:
            score -= 25
        if vis < 5000:
            score -= 20
        if hum > 85:
            score -= 10
    elif act == "flying":
        if is_thunder(s.code(i)):
            score -= 90
        if vis < 5000:
            score -= (5000 - vis) / 100
        if gust > 36:
            score -= (gust - 36) * 2
        if s.wet(i):
            score -= 20
    return max(0.0, min(100.0, score))


def tone_for(score):
    return "good" if score >= 75 else "ok" if score >= 55 else "caution" if score >= 35 else "warn"


def main_issue(s, i):
    if is_thunder(s.code(i)):
        return "thunderstorm risk"
    mm = s.precip(i)
    if mm >= 7.6:
        return "heavy rain"
    if mm >= 0.2:
        return "rain"
    if s.pop(i) >= 60:
        return "a high chance of rain"
    if s.feels(i) >= 41:
        return "dangerous heat"
    if s.feels(i) >= 36:
        return "heat and humidity"
    if s.gust(i) >= 45:
        return "strong gusts"
    if s.vis(i) < 1000:
        return "poor visibility"
    if s.aqi and s.aqi > 150 and (i - s.i0) <= 12:
        return "poor air quality"
    if not s.is_day(i):
        return "darkness"
    if s.temp(i) < 12:
        return "cold"
    return "mixed conditions"


def window_metrics(s, a, L):
    idx = range(a, a + L)
    return {
        "temp_min": round(min(s.temp(i) for i in idx)), "temp_max": round(max(s.temp(i) for i in idx)),
        "pop_max": int(max(s.pop(i) for i in idx)), "rain_mm": round(sum(s.precip(i) for i in idx), 1),
        "wind_max": round(max(s.wind(i) for i in idx)), "gust_max": round(max(s.gust(i) for i in idx)),
        "uv_max": round(max(s.uv(i) for i in idx), 1), "vis_km": round(min(s.vis(i) for i in idx) / 1000, 1),
        "feels_max": round(max(s.feels(i) for i in idx)), "cloud": round(sum(s.cloud(i) for i in idx) / L),
    }


def window_why(s, a, L, act):
    m = window_metrics(s, a, L)
    p = ACT.get(act, ACT["outdoor"])
    why = []
    lo, hi = p["ideal"]
    if lo <= m["temp_min"] and m["temp_max"] <= hi:
        why.append(f"{m['temp_min']}–{m['temp_max']}°C is comfortable" if m["temp_min"] != m["temp_max"] else f"{m['temp_max']}°C is comfortable")
    elif act in ("laundry", "spray", "photo", "stargaze", "flying"):
        why.append(f"{m['temp_min']}–{m['temp_max']}°C")
    if m["rain_mm"] < 0.1 and m["pop_max"] <= 20:
        why.append(f"very low rain chance ({m['pop_max']}%)")
    elif m["rain_mm"] < 0.1:
        why.append(f"no rain forecast (chance up to {m['pop_max']}%)")
    if m["gust_max"] < 22:
        why.append("light wind")
    elif m["gust_max"] < 35:
        why.append("manageable wind")
    if act not in ("stargaze",) and m["uv_max"] <= 3:
        why.append("gentle sun (low UV)")
    if m["vis_km"] >= 8:
        why.append("clear visibility")
    if s.aqi is not None and s.aqi <= 50 and (a - s.i0) <= 12 and p.get("aqi"):
        why.append("clean air")
    if act == "laundry":
        hum = round(sum(s.hum(i) for i in range(a, a + L)) / L)
        why.append(f"humidity around {hum}% helps clothes dry")
    if act == "spray":
        why.append(f"wind under {max(m['wind_max'], 1)} km/h keeps spray from drifting")
    return why[:5]


def best_windows(s, act, start_i, end_i, min_len=1, max_len=3, k=3, min_score=55):
    start_i = max(0, start_i)
    end_i = min(s.n, end_i)
    if end_i - start_i < min_len:
        return []
    scores = {i: score_hour(act, s, i) for i in range(start_i, end_i)}
    cands = []
    for L in range(min_len, max_len + 1):
        for a in range(start_i, end_i - L + 1):
            seg = [scores[j] for j in range(a, a + L)]
            if min(seg) < min_score:
                continue
            avg = sum(seg) / L
            cands.append((avg + (L - min_len) * 1.5, a, L, avg))
    cands.sort(reverse=True)
    picked, used = [], set()
    for _, a, L, avg in cands:
        span = set(range(a, a + L))
        if span & used:
            continue
        m = window_metrics(s, a, L)
        picked.append({
            "start_i": a, "len": L, "score": round(avg), "tone": tone_for(avg),
            "day": s.day_name(a), "start": s.label(a), "end": s.label(a + L) if a + L < s.n else "",
            "range": f"{s.label(a)} – {s.label(a + L)}", "metrics": m,
            "why": window_why(s, a, L, act), "confidence": s.conf(a),
        })
        used |= span | {a - 1, a + L}
        if len(picked) >= k:
            break
    return picked


def bad_spans(s, act, start_i, end_i, thresh=38):
    spans, cur = [], None
    day_only = ACT.get(act, {}).get("day", False) or act in ("laundry", "spray", "photo")
    for i in range(max(0, start_i), min(s.n, end_i)):
        hr = s.dt(i).hour
        if act != "stargaze" and (hr < 5 or hr >= 23):
            bad = False  # nobody plans these at 3 AM
        else:
            bad = score_hour(act, s, i) < thresh and (s.is_day(i) or not day_only)
        if bad and cur is None:
            cur = [i, i]
        elif bad:
            cur[1] = i
        elif cur is not None:
            spans.append(tuple(cur))
            cur = None
    if cur:
        spans.append(tuple(cur))
    out = []
    for a, b in spans[:3]:
        out.append({"range": f"{s.label(a)} – {s.label(b + 1)}", "day": s.day_name(a), "issue": main_issue(s, a)})
    return out


# ------------------------------------------------------------------ rain
def _spans(idx):
    spans = []
    for i in idx:
        if spans and i == spans[-1][1] + 1:
            spans[-1][1] = i
        else:
            spans.append([i, i])
    return spans


def rain_outlook(s, a, b):
    hrs = list(range(max(0, a), min(b, s.n)))
    wet = [i for i in hrs if s.wet(i)]
    return {
        "wet": wet, "spans": _spans(wet), "hours": hrs,
        "total": round(sum(s.precip(i) for i in hrs), 1),
        "peak": round(max((s.precip(i) for i in hrs), default=0), 1),
        "maxpop": int(max((s.pop(i) for i in hrs), default=0)),
        "chance": any(s.pop(i) >= 30 for i in hrs),
    }


def rain_sentence(s, a, b, when="in this period"):
    ro = rain_outlook(s, a, b)
    if ro["spans"]:
        parts = []
        for x, y in ro["spans"][:2]:
            parts.append(f"around {s.label(x)}" if x == y else f"between {s.label(x)} and {s.label(y + 1)}")
        txt = "Rain looks likely " + " and ".join(parts)
        if ro["total"] >= 0.2:
            txt += f" — about {ro['total']} mm in total ({rain_words(ro['peak'])} at its strongest)"
        return txt + "."
    if ro["chance"]:
        return f"A passing shower is possible (up to {ro['maxpop']}% chance) but most of {when} should stay dry."
    return f"No rain expected {when} (chance stays under {max(ro['maxpop'], 5)}%)."


# ------------------------------------------------------------------ risks
def compound_risks(s, a=None, b=None, heat_shift=0):
    a = s.i0 if a is None else a
    b = min(s.n, (a + 24) if b is None else b)
    rs = []
    idx = range(a, b)

    def add(level, key, icon, title, what, why, do, i_from, i_to=None):
        when = f"{s.day_name(i_from)} {s.label(i_from)}" + (f" – {s.label(i_to + 1)}" if i_to is not None and i_to != i_from else "")
        rs.append({"key": key, "level": level, "icon": icon, "title": title, "what": what, "why": why, "do": do, "when": when})

    # heat + humidity
    hot = [i for i in idx if s.feels(i) >= 41 - heat_shift]
    if hot:
        sp = _spans(hot)[0]
        peak = max(s.feels(i) for i in hot)
        lvl = 3 if peak >= 46 - heat_shift else 2
        hum = round(sum(s.hum(i) for i in hot) / len(hot))
        add(lvl, "heat", "🥵", "Dangerous heat" if lvl == 3 else "Very hot and sticky",
            f"It will feel like {round(peak)}°C at its worst (humidity around {hum}%).",
            "Humid air stops sweat from cooling your body, so the heat feels stronger than the thermometer says.",
            ["Do outdoor work before 11 AM or after 5 PM", "Drink water regularly, even if not thirsty", "Take breaks in shade or AC"], sp[0], sp[1])
    else:
        muggy = [i for i in idx if s.temp(i) >= 33 and s.hum(i) >= 65 and s.is_day(i)]
        if muggy:
            sp = _spans(muggy)[0]
            add(1, "muggy", "😓", "Muggy afternoon", f"About {round(max(s.temp(i) for i in muggy))}°C with humid air.",
                "Warm + humid = you tire faster outdoors.", ["Prefer light cotton clothes", "Keep water handy"], sp[0], sp[1])
    # thunderstorm
    th = [i for i in idx if is_thunder(s.code(i))]
    if th:
        sp = _spans(th)[0]
        add(3, "storm", "⛈️", "Thunderstorm risk", "Thunder and lightning are forecast.",
            "Lightning is the main danger outdoors — open fields, trees and water are worst.",
            ["Avoid open ground, trees and water", "Unplug sensitive electronics", "Delay outdoor plans until it passes"], sp[0], sp[1])
    else:
        prone = [i for i in idx if s.cape(i) >= 1500 and s.pop(i) >= 40]
        if prone:
            sp = _spans(prone)[0]
            add(2, "stormprone", "🌩️", "Storm-prone hours", "The air is unstable, so a sudden thunderstorm is possible.",
                "High atmospheric energy plus decent rain chance often means a short, sharp storm.",
                ["Keep an eye on the sky", "Have a shelter plan for outdoor events"], sp[0], sp[1])
    # heavy rain
    hv = [i for i in idx if s.precip(i) >= 7.6]
    if hv:
        sp = _spans(hv)[0]
        peak = max(s.precip(i) for i in hv)
        lvl = 3 if peak >= 35 else 2
        add(lvl, "heavyrain", "🌧️", "Heavy rain", f"Up to {round(peak, 1)} mm per hour ({rain_words(peak)}).",
            "Downpours like this can flood low roads and slow traffic badly.",
            ["Avoid low-lying roads and underpasses", "Leave earlier or wait it out", "Keep phone charged"], sp[0], sp[1])
    # rain + wind
    rw = [i for i in idx if s.precip(i) >= 1 and s.gust(i) >= 40 and i not in hv]
    if rw:
        sp = _spans(rw)[0]
        add(2, "wetwind", "🌬️", "Wet and gusty", f"Rain together with gusts up to {round(max(s.gust(i) for i in rw))} km/h.",
            "Wind makes rain sideways and harder to ride or walk in, and umbrellas can fail.",
            ["Prefer a raincoat over an umbrella", "Two-wheeler riders: slow down, grip firmly"], sp[0], sp[1])
    # visibility
    fg = [i for i in idx if s.vis(i) < 1000]
    if fg:
        sp = _spans(fg)[0]
        lvl = 3 if min(s.vis(i) for i in fg) < 200 else 2
        add(lvl, "fog", "🌫️", "Low visibility", f"Visibility drops to about {round(min(s.vis(i) for i in fg) / 1000, 1)} km.",
            "Fog or haze makes roads and runways unsafe.", ["Drive slowly with low-beam lights", "Allow extra travel time"], sp[0], sp[1])
    # air
    if s.aqi and s.aqi >= 101 and a <= s.i0 + 1:
        band = aqi_band(s.aqi)
        lvl = 3 if s.aqi >= 201 else 2 if s.aqi >= 151 else 1
        add(lvl, "air", "😷", f"Air quality: {band['label']}", f"US AQI is {round(s.aqi)}" + (f" (PM2.5 {round(float(s.pm25))} µg/m³)." if s.pm25 else "."),
            "Fine dust can irritate lungs — kids, elders and people with asthma feel it first.",
            [band["advice"]], s.i0)
    # UV
    uvh = [i for i in idx if s.uv(i) >= 8]
    if uvh:
        sp = _spans(uvh)[0]
        add(1 if max(s.uv(i) for i in uvh) < 11 else 2, "uv", "🕶️", f"UV is {uv_band(max(s.uv(i) for i in uvh))}",
            f"UV index reaches {round(max(s.uv(i) for i in uvh))}.", "Strong sun can burn unprotected skin in 15–25 minutes.",
            ["Sunscreen + cap or umbrella", "Avoid direct midday sun"], sp[0], sp[1])
    # cold
    cold = [i for i in idx if s.temp(i) <= 8]
    if cold:
        sp = _spans(cold)[0]
        add(1, "cold", "🥶", "Cold spell", f"Temperature drops to {round(min(s.temp(i) for i in cold))}°C.", "Cold air and wind chill are hard on elders and kids.",
            ["Layer up, cover ears and hands"], sp[0], sp[1])
    rs.sort(key=lambda r: -r["level"])
    return rs


# ------------------------------------------------------------------ now / plan
def now_block(s):
    i = s.i0
    c = s.cur
    temp = float(c.get("temperature_2m", s.temp(i)))
    feels = float(c.get("apparent_temperature", s.feels(i)))
    code = c.get("weather_code", s.code(i))
    day = bool(c.get("is_day", s.is_day(i)))
    text, emoji = describe(code, day)
    wind = float(c.get("wind_speed_10m", s.wind(i)))
    return {
        "temp": round(temp), "feels": round(feels), "humidity": round(float(c.get("relative_humidity_2m", s.hum(i)))),
        "wind": round(wind), "gust": round(float(c.get("wind_gusts_10m", s.gust(i)))), "wind_dir": compass(c.get("wind_direction_10m")),
        "cloud": round(float(c.get("cloud_cover", s.cloud(i)))), "code": code, "text": text, "emoji": emoji, "is_day": day,
        "uv": round(s.uv(i), 1), "uv_band": uv_band(s.uv(i)), "vis_km": round(s.vis(i) / 1000, 1),
        "pressure": c.get("pressure_msl"), "rain_now": round(float(c.get("precipitation", s.precip(i))), 1),
        "feels_words": feels_words(feels), "wind_words": wind_words(wind),
    }


def layman_now(s, place_name=None):
    nb = now_block(s)
    place = place_name or s.name
    lines = [f"It's {nb['temp']}°C in {place} right now — {nb['text']}."]
    if abs(nb["feels"] - nb["temp"]) >= 3:
        if nb["feels"] > nb["temp"]:
            why = "the air is humid, so sweat can't cool you" if nb["humidity"] >= 60 else "of the warm air and sun"
        else:
            why = "the wind is carrying heat away"
        lines.append(f"It feels like {nb['feels']}°C because {why}.")
    i = s.i0
    if s.precip(i) >= 0.2:
        end = next((j for j in range(i, min(s.n, i + 24)) if not s.wet(j)), None)
        lines.append(f"It's raining now ({rain_words(s.precip(i))})" + (f" and should ease around {s.label(end)}." if end else " and may continue for a while."))
    else:
        nxt = next((j for j in range(i + 1, min(s.n, i + 25)) if s.wet(j)), None)
        if nxt is None:
            lines.append("No rain is expected for the next 24 hours.")
        else:
            gap = nxt - i
            lines.append(f"No rain right now, but it looks likely {s.day_name(nxt).lower() if s.day_name(nxt) != 'Today' else 'today'} around {s.label(nxt)} (in about {gap} hour{'s' if gap != 1 else ''}).")
    if nb["wind"] >= 25:
        lines.append(f"It's {nb['wind_words']} ({nb['wind']} km/h, gusts to {nb['gust']}).")
    if s.aqi is not None:
        b = aqi_band(s.aqi)
        lines.append(f"Air quality is {b['label'].lower()} (US AQI {round(s.aqi)}).")
    return nb, lines


def headline(s, nb=None):
    nb = nb or now_block(s)
    i = s.i0
    if s.precip(i) >= 0.2:
        return "It's raining right now", "rain"
    nxt = next((j for j in range(i + 1, min(s.n, i + 7)) if s.wet(j)), None)
    if any(is_thunder(s.code(j)) for j in range(i, min(s.n, i + 12))):
        return "Thunderstorms possible today", "storm"
    if nxt is not None:
        return f"Rain likely around {s.label(nxt)}", "rain"
    if nb["feels"] >= 41:
        return "Very hot — take care outdoors", "heat"
    if s.aqi and s.aqi > 150:
        return "Air quality is poor today", "air"
    if nb["feels"] >= 35:
        return "Hot and sticky, but dry", "warm"
    if nb["feels"] >= 30:
        return "Warm and dry", "warm"
    if nb["feels"] >= 22:
        return "Pleasant and dry", "good"
    return "Cool and calm", "cool"


BLOCKS = [("Morning", 6, 12, "🌅"), ("Afternoon", 12, 17, "☀️"), ("Evening", 17, 21, "🌇"), ("Night", 21, 29, "🌙")]


def day_plan(s, day_offset=0):
    date = s.now_dt.date() + timedelta(days=day_offset)
    out = []
    for name, h1, h2, icon in BLOCKS:
        base = datetime(date.year, date.month, date.day)
        a_dt, b_dt = base + timedelta(hours=h1), base + timedelta(hours=h2)
        idx = [i for i in range(s.n) if a_dt <= s.dt(i) < b_dt and i >= (s.i0 if day_offset == 0 else 0)]
        if not idx:
            continue
        scores = [score_hour("walking" if name != "Night" else "commute", s, i) for i in idx]
        avg, worst = sum(scores) / len(scores), min(scores)
        tone = tone_for(min(avg, worst + 25))
        temps = [s.temp(i) for i in idx]
        mm = sum(s.precip(i) for i in idx)
        popmax = int(max(s.pop(i) for i in idx))
        wi = next((i for i in idx if s.wet(i)), None)
        if any(is_thunder(s.code(i)) for i in idx):
            title = "Thunderstorms possible"
        elif wi is not None and mm >= 0.2:
            title = f"Rain likely from {s.label(wi)}"
        elif popmax >= 40:
            title = "Showers possible"
        elif max(s.feels(i) for i in idx) >= 40:
            title = "Very hot and sticky"
        elif tone == "good":
            title = "Good outdoor window" if name != "Night" else "Calm and comfortable"
        else:
            title = "Mostly fine"
        code = max((s.code(i) for i in idx), default=0)
        emoji = describe(code, name != "Night")[1]
        detail = f"{round(min(temps))}–{round(max(temps))}°C · {popmax}% rain chance · {wind_words(sum(s.wind(i) for i in idx) / len(idx))}"
        out.append({"label": name, "range": f"{h12(a_dt)}–{h12(b_dt)}", "tone": tone, "title": title, "detail": detail,
                    "emoji": emoji or icon, "pop": popmax, "temp_min": round(min(temps)), "temp_max": round(max(temps)), "rain_mm": round(mm, 1)})
    return out


def hourly_strip(s, a=None, n=24, act="walking"):
    a = s.i0 if a is None else a
    out = []
    for i in range(a, min(s.n, a + n)):
        text, emoji = describe(s.code(i), s.is_day(i))
        sc = score_hour(act, s, i)
        out.append({"label": s.label(i), "hour": s.dt(i).hour, "day": s.day_name(i), "temp": round(s.temp(i)), "pop": int(s.pop(i)),
                    "mm": round(s.precip(i), 1), "emoji": emoji, "text": text, "is_day": s.is_day(i), "score": round(sc), "tone": tone_for(sc),
                    "wind": round(s.wind(i)), "i": i})
    return out


def daily_list(s):
    out = []
    d = s.daily
    for k, date_str in enumerate(d.get("time", [])):
        if date_str < s.now_dt.date().isoformat():
            continue
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        diff = (dt.date() - s.now_dt.date()).days
        label = "Today" if diff == 0 else "Tomorrow" if diff == 1 else dt.strftime("%a")
        code = (d.get("weather_code") or [0])[k]
        mm = (d.get("precipitation_sum") or [0])[k] or 0
        pop = (d.get("precipitation_probability_max") or [0])[k]
        hi = (d.get("temperature_2m_max") or [0])[k]
        lo = (d.get("temperature_2m_min") or [0])[k]
        text, emoji = describe(code, True)
        out.append({"label": label, "date": date_str, "emoji": emoji, "text": text, "hi": round(hi), "lo": round(lo), "rain_mm": round(mm, 1),
                    "pop": int(pop) if pop is not None else None, "date_short": f"{dt.day} {dt.strftime('%b')}"})
    return out


# ------------------------------------------------------------------ personal (Weather Twin lite)
def commute_notes(s, profile):
    notes = []
    am, pm = int(profile.get("am", 9)), int(profile.get("pm", 18))
    for word, hour in (("morning", am), ("evening", pm)):
        target = None
        for off in (0, 1):
            date = (s.now_dt.date() + timedelta(days=off)).isoformat()
            i = s.idx(date, hour)
            if i is not None and i >= s.i0:
                target = i
                break
        if target is None:
            continue
        span = [target, target + 1]
        wet = [j for j in span if s.wet(j)]
        day = s.day_name(target).lower()
        if wet:
            better = next((t for t in (target - 1, target - 2, target + 2, target + 3) if t >= s.i0 and not any(s.wet(j) for j in (t, t + 1))), None)
            tip = f" Leaving around {s.label(better)} avoids it." if better is not None else " Carry a raincoat."
            notes.append({"tone": "caution", "when": word, "text": f"Rain overlaps your usual {h12(s.dt(target))} {word} commute ({day}).{tip}"})
        else:
            notes.append({"tone": "good", "when": word, "text": f"Your usual {h12(s.dt(target))} {word} commute ({day}) looks dry."})
    return notes


# ------------------------------------------------------------------ anomaly
def anomaly(s, clim):
    if not clim:
        return None
    date = s.now_dt.date().isoformat()
    di = s.daily_i(date)
    if di is None:
        return None
    hi = s.daily.get("temperature_2m_max", [None])[di]
    if hi is None:
        return None
    diff = hi - clim["mean"]
    if abs(diff) < 2.5:
        return None
    word = "higher" if diff > 0 else "lower"
    return {"kind": "temperature", "diff": round(diff, 1), "today": round(hi, 1), "baseline": clim["mean"],
            "text": f"Today's high ({round(hi)}°C) is {abs(round(diff, 1))}°C {word} than the average for this time of year in {s.name} "
                    f"({clim['mean']}°C, based on the last {clim['years']} years, ±3 days around today)."}


# ------------------------------------------------------------------ sky (drives the animated background)
def sky_block(s):
    nb = now_block(s)
    date = s.now_dt.date().isoformat()
    sr, ss = s.sun(date)
    fog = s.vis(s.i0) < 1500 or (nb["code"] in (45, 48))
    thunder = any(is_thunder(s.code(j)) for j in range(s.i0, min(s.n, s.i0 + 2)))
    return {
        "local_time": s.now_dt.strftime(FMT), "sunrise": sr.strftime(FMT) if sr else None, "sunset": ss.strftime(FMT) if ss else None,
        "is_day": nb["is_day"], "cloud": nb["cloud"], "rain": nb["rain_now"], "wind": nb["wind"], "gust": nb["gust"],
        "code": nb["code"], "fog": bool(fog), "thunder": bool(thunder),
        "theme": "storm" if thunder else "rain" if nb["rain_now"] >= 0.1 else "night" if not nb["is_day"] else "clear-day",
    }


# ------------------------------------------------------------------ suggestions (live chips)
def suggestions(s, persona="office", profile=None, risks=None, limit=6):
    profile = profile or {}
    out = []
    nb = now_block(s)
    i = s.i0
    night = not nb["is_day"]
    raining = s.precip(i) >= 0.2
    rain_soon = next((j for j in range(i + 1, min(s.n, i + 9)) if s.wet(j)), None)

    def add(q, kind="tip", why=""):
        if all(x["q"] != q for x in out):
            out.append({"q": q, "kind": kind, "why": why})

    if raining:
        add("When will the rain stop?", "alert", "Raining now")
        add("Is it safe to ride a bike now?", "alert")
    elif rain_soon is not None:
        add(f"Will rain affect me around {s.label(rain_soon)}?", "alert", "Rain soon")
        add("Do I need an umbrella today?", "alert")
    if risks:
        top = risks[0]
        if top["key"] in ("heat", "muggy"):
            add("When is the coolest time to go out today?", "alert", top["title"])
        if top["key"] in ("storm", "stormprone"):
            add("Is it safe to be outside during the storm?", "alert", top["title"])
        if top["key"] == "air":
            add("Is the air safe for a walk today?", "alert", top["title"])
        if top["key"] == "fog":
            add("How bad is the fog on the roads?", "alert", top["title"])
    if nb["feels"] >= 36 and not raining:
        add("What should I wear in this heat?")
    if night:
        add("What will tomorrow morning be like?")
        add("Good night for stargazing?")
    else:
        if not raining and rain_soon is None and nb["humidity"] < 80:
            add("Should I dry clothes outside today?")
    add("Best time for a run tomorrow?")
    add("Any weather alerts near me?", "alert" if risks else "tip")
    if persona in ("office", "student", "commuter"):
        add("Will it rain when I head home?")
    if persona == "delivery":
        add("Which hours are roughest for riding today?")
    if persona == "farmer":
        add("Best time to spray crops?")
        add("Do I need to irrigate?")
    if persona == "fisherman":
        add("Is it safe to go out to sea?")
    if persona == "fitness":
        add("Best time to cycle tomorrow?")
    if persona == "parent":
        add("When is it safe for kids to play outside?")
    if persona == "traveler":
        add("Plan my next 3 days")
    fav = (profile.get("fav") or "").strip()
    if fav:
        add(f"Best time for {act_label(fav)} today?", "tip", "Your usual")
    add("What if I leave 1 hour later?")
    add("Plan my day")
    return out[:limit]


# ------------------------------------------------------------------ what-if
def what_if(s, i1, i2, act="outdoor"):
    def col(i):
        return {"label": f"{s.day_name(i)} {s.label(i)}" if s.day_name(i) != "Today" else s.label(i),
                "temp": f"{round(s.temp(i))}°C", "feels": f"{round(s.feels(i))}°C", "pop": f"{int(s.pop(i))}%",
                "rain": f"{round(s.precip(i), 1)} mm", "wind": f"{round(s.wind(i))} km/h", "vis": f"{round(s.vis(i) / 1000, 1)} km",
                "score": round(score_hour(act, s, i)), "issue": main_issue(s, i)}
    a, b = col(i1), col(i2)
    rows = [
        {"label": "Temperature", "values": [a["temp"], b["temp"]]}, {"label": "Feels like", "values": [a["feels"], b["feels"]]},
        {"label": "Rain chance", "values": [a["pop"], b["pop"]]}, {"label": "Rain amount", "values": [a["rain"], b["rain"]]},
        {"label": "Wind", "values": [a["wind"], b["wind"]]}, {"label": "Visibility", "values": [a["vis"], b["vis"]]},
        {"label": "Comfort score", "values": [f"{a['score']}/100", f"{b['score']}/100"]},
    ]
    diff = a["score"] - b["score"]
    if abs(diff) < 8:
        verdict = f"Both times are similar for {act_label(act)} — pick whichever suits your schedule."
    else:
        better, worse, bi, wi = (a, b, i1, i2) if diff > 0 else (b, a, i2, i1)
        why = []
        if s.pop(wi) - s.pop(bi) >= 20:
            why.append(f"rain chance jumps from {int(s.pop(bi))}% to {int(s.pop(wi))}%")
        if s.gust(wi) - s.gust(bi) >= 8:
            why.append("the wind picks up")
        if s.feels(wi) - s.feels(bi) >= 3:
            why.append("it feels hotter")
        if not why:
            why.append(f"{worse['issue']} is more of a factor")
        verdict = f"{better['label']} looks better for {act_label(act)}: at {worse['label']}, " + " and ".join(why) + "."
    return {"columns": [a["label"], b["label"]], "rows": rows, "verdict": verdict, "scores": [a["score"], b["score"]]}


# ------------------------------------------------------------------ briefing (Home / chat opener)
def briefing(s, profile=None, clim=None, persona="office"):
    profile = profile or {}
    heat_shift = {"low": 3, "high": -2}.get(profile.get("heat"), 0)
    nb, lines = layman_now(s)
    head, head_kind = headline(s, nb)
    risks = compound_risks(s, heat_shift=heat_shift)
    bw = best_windows(s, "outdoor", s.i0, min(s.n, s.i0 + 30), 1, 3, k=1)
    plan_today = day_plan(s, 0)
    plan = plan_today if len(plan_today) >= 2 else plan_today + day_plan(s, 1)[:4 - len(plan_today)]
    an = anomaly(s, clim)
    b = aqi_band(s.aqi)
    return {
        "place": s.name, "lat": s.place.get("lat"), "lon": s.place.get("lon"), "updated": hm12(s.now_dt), "source": s.source,
        "now": nb, "headline": head, "headline_kind": head_kind, "sentences": lines, "plan": plan,
        "best_window": bw[0] if bw else None, "risks": risks[:4], "hourly": hourly_strip(s, n=24), "daily": daily_list(s),
        "aqi": ({"value": round(s.aqi), **b} if b else None), "anomaly": an, "commute": commute_notes(s, profile),
        "sun": {"sunrise": (s.sun(s.now_dt.date().isoformat())[0] or s.now_dt).strftime("%I:%M %p").lstrip("0") if s.sun(s.now_dt.date().isoformat())[0] else None,
                "sunset": (s.sun(s.now_dt.date().isoformat())[1] or s.now_dt).strftime("%I:%M %p").lstrip("0") if s.sun(s.now_dt.date().isoformat())[1] else None},
        "suggestions": suggestions(s, persona, profile, risks), "sky": sky_block(s), "confidence": s.conf(s.i0 + 3),
    }
