"""
Chat brain. Understands questions with rules (no LLM needed), fetches real data,
and answers with the engine's numbers. Gemini (if working) only handles free-form
questions, non-English input/output.
"""
import json
import logging
import re
from datetime import timedelta

from . import advisory, alerts_engine, cities, engine as E, gemini_service as G, openmeteo as om, routeeng, snapshot
from .wxcodes import aqi_band, describe, rain_words, uv_band, wind_words

log = logging.getLogger("weathergpt.chat")

ACT_WORDS = [
    ("laundry", r"laundry|dry (my |the )?(clothes|washing)|hang (my |the )?(clothes|washing)|wash(ing)? (my |the )?clothes|clothes.*dry"),
    ("spray", r"spray|pesticide|insecticide|fertili[sz]er"),
    ("stargaze", r"star ?gaz|milky way|night sky|telescope"),
    ("photo", r"photo|photograph|golden hour|sunset pic|sunrise pic|shoot"),
    ("cycling", r"cycl|bicycle"),
    ("running", r"\brun\b|running|jog|marathon"),
    ("walking", r"\bwalk|stroll|hike|hiking|trek"),
    ("picnic", r"picnic|barbecue|bbq|cricket|football|match|outdoor (event|party|wedding|plan)|wedding|party"),
    ("riding", r"\bbike\b|motorcycle|scooter|two.?wheeler|\bride\b|riding"),
    ("commute", r"commute|office|leave for|head home|go home|drive|driving|travel"),
    ("kids", r"\bkids?\b|children|child\b|play outside|playground"),
    ("flying", r"\bfly\b|flight|drone|flying"),
]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
LANGS = {"hi": "Hindi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "bn": "Bengali", "ml": "Malayalam", "mr": "Marathi", "gu": "Gujarati", "pa": "Punjabi"}


# ------------------------------------------------------------------ parsing
def detect_activity(t):
    for act, pat in ACT_WORDS:
        if re.search(pat, t):
            return act
    return None


def detect_intent(t, act, places):
    if re.search(r"what if|instead of|rather than|compare|later than|earlier than", t) or re.search(r"\b(leave|go|start|head)\b.*\b(later|earlier)\b", t):
        return "whatif"
    if re.search(r"\bfrom\b.+\bto\b", t) or (len(places) >= 2 and re.search(r"\bto\b|->|→|route|trip|travel|drive|going|reach|journey|road", t)):
        return "route"
    if re.search(r"\bsea\b|wave|fishing|boat|harbou?r|fishermen", t):
        return "sea"
    if re.search(r"irrigat|water (my |the )?(crop|plant|field|farm)|watering", t):
        return "irrigate"
    if re.search(r"worst|roughest|toughest|avoid|bad time|not to go|shouldn.t go", t) and (act or re.search(r"time|hour", t)):
        return "window"
    if re.search(r"best time|when (should|can|could|is|would|to)\b|good time|right time|ideal time|perfect (time|window)|which hour|what time", t):
        return "window"
    if act and act != "commute":
        return "window"
    if re.search(r"plan my|my day|schedule|itinerary|what matters|next \d+ days|this week|weekend|3 days|three days", t):
        return "plan"
    if re.search(r"alert|warning|cyclone|flood|danger|emergency|disaster", t):
        return "alerts"
    if re.search(r"\bwear\b|dress|jacket|sweater|outfit|what to carry|should i carry|carry", t):
        return "wear"
    if re.search(r"rain|umbrella|drizzle|shower|monsoon|wet|thunder|storm|lightning|raincoat", t):
        return "rain"
    if re.search(r"aqi|air quality|pollution|smog|breath|mask|dust|air (is|safe)", t):
        return "air"
    if re.search(r"\bwind|windy|gust|breeze", t):
        return "wind"
    if re.search(r"\buv\b|sunscreen|sunburn|sun protection", t):
        return "uv"
    if re.search(r"\bfog|visibility|haze|misty", t):
        return "vis"
    if re.search(r"hot|cold|warm|temperature|\btemp\b|heat|humid|sweat|cool|degrees|freez|chill|sticky", t):
        return "temp"
    if re.search(r"weather|forecast|outlook|what.?s it like|how.?s it|be like|going to be", t):
        return "summary"
    if act == "commute":
        return "window"
    return "general"


def parse_hour(t):
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if m:
        h = int(m.group(1)) % 12
        return h + (12 if m.group(3) == "pm" else 0)
    m = re.search(r"\b(?:at|by|around|@)\s*(\d{1,2})\b(?!\s*(?:km|mm|c\b|°|%))", t)
    if m:
        h = int(m.group(1))
        if h > 24:
            return None
        return h + 12 if 1 <= h <= 6 else h
    return None


def resolve_when(text, s):
    t = text.lower()
    day_offset, explicit = 0, False
    if re.search(r"day after tomorrow|day after tmrw", t):
        day_offset, explicit = 2, True
    elif re.search(r"\btomorrow\b|\btom\b|\btmrw\b|\btmr\b|\bnext day\b", t):
        day_offset, explicit = 1, True
    elif re.search(r"\btoday\b|tonight|this (morning|afternoon|evening)|right now|\bnow\b|currently", t):
        day_offset, explicit = 0, True
    else:
        for k, wd in enumerate(WEEKDAYS):
            if re.search(r"\b" + wd[:3] + r"(?:day|sday|nesday|rsday|urday)?\b", t) and wd in t:
                diff = (k - s.now_dt.weekday()) % 7 or 7
                day_offset, explicit = diff, True
                break
    part = None
    for name, (h1, h2) in {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 21), "night": (19, 29)}.items():
        if re.search(name, t):
            part = (name, h1, h2)
    if re.search(r"\bright now\b|\bnow\b|currently|at the moment", t) and day_offset == 0:
        return {"a": s.i0, "b": min(s.n, s.i0 + 2), "label": "right now", "day_offset": 0, "hour": None, "explicit": True}
    hour = parse_hour(t)
    if hour is not None:
        if not explicit and hour < s.now_dt.hour:
            day_offset = 1
        date = (s.now_dt.date() + timedelta(days=day_offset)).isoformat()
        i = s.idx(date, hour % 24)
        if i is not None:
            return {"a": i, "b": min(s.n, i + 2), "label": f"at {s.label(i)}" + ("" if day_offset == 0 else f" {s.day_name(i).lower()}"), "day_offset": day_offset, "hour": hour, "explicit": True}
    if part:
        name, h1, h2 = part
        rng = s.day_range(day_offset if name != "night" or day_offset else 0, 0, 24)
        if rng:
            base = s.now_dt.date() + timedelta(days=day_offset)
            from datetime import datetime as _dt
            start = _dt(base.year, base.month, base.day) + timedelta(hours=h1)
            end = _dt(base.year, base.month, base.day) + timedelta(hours=h2)
            idx = [i for i in range(s.n) if start <= s.dt(i) < end and i >= s.i0]
            if idx:
                lab = ("tonight" if name == "night" and day_offset == 0 else f"{'today' if day_offset == 0 else s.day_name(idx[0]).lower()} {name}")
                return {"a": idx[0], "b": idx[-1] + 1, "label": lab, "day_offset": day_offset, "hour": None, "explicit": True}
    if day_offset == 0:
        if explicit:
            rng = s.day_range(0, 0, 24)
            return {"a": s.i0, "b": max(s.i0 + 1, rng[1]) if rng else s.i0 + 12, "label": "today", "day_offset": 0, "hour": None, "explicit": True}
        return {"a": s.i0, "b": min(s.n, s.i0 + 24), "label": "in the next 24 hours", "day_offset": 0, "hour": None, "explicit": False}
    rng = s.day_range(day_offset, 5, 23)
    if rng:
        return {"a": rng[0], "b": rng[1], "label": s.day_name(rng[0]).lower() if day_offset > 1 else "tomorrow", "day_offset": day_offset, "hour": None, "explicit": True}
    return {"a": s.i0, "b": min(s.n, s.i0 + 24), "label": "in the next 24 hours", "day_offset": 0, "hour": None, "explicit": False}


async def find_places(text):
    hits = cities.find_in_text(text)
    out = [{"name": c["name"].split(" (")[0], "lat": c["lat"], "lon": c["lon"], "state": c["state"]} for c in hits]
    if not out:
        m = re.search(r"\b(?:in|at|for|near|around)\s+([A-Za-z][A-Za-z\.\- ]{2,30}?)(?=\s+(?:today|tomorrow|tonight|tom|now|this|next|at|by|on|then|and|\?)|[,\?\.!]|$)", text)
        if m and m.group(1).lower() not in ("the", "my", "our", "your", "this", "that", "time", "case", "general", "advance"):
            try:
                res = await om.geocode(m.group(1).strip(), count=1)
                if res:
                    out.append({"name": res[0]["name"], "lat": res[0]["lat"], "lon": res[0]["lon"], "state": res[0].get("state") or ""})
            except Exception:  # noqa: BLE001
                pass
    return out


# ------------------------------------------------------------------ handlers
def cap1(x):
    return x[:1].upper() + x[1:] if x else x


def _strip_block(s, a, b, limit=12):
    items = E.hourly_strip(s, a, min(limit, max(1, b - a)))
    return {"type": "strip", "items": items}


def _window_answer(s, act, when, text):
    lab = E.act_label(act)
    a, b = when["a"], when["b"]
    if re.search(r"worst|roughest|toughest|avoid|bad time|not to go|shouldn.t go", text.lower()):
        rng_b = min(s.n, max(b, s.i0 + 24))
        bad = E.bad_spans(s, act, a, rng_b, thresh=45)
        if not bad:
            return f"Good news — no really bad hours for {lab} {when['label']}.", [], s.conf(a)
        return (f"The roughest time for {lab} is **{bad[0]['day']} {bad[0]['range']}** ({bad[0]['issue']}).", [{"type": "avoid", "items": bad}], s.conf(a))
    if not when["explicit"]:
        b = min(s.n, s.i0 + 36)
    elif when["day_offset"] == 0 and b - a < 3:
        b = min(s.n, s.i0 + 24)
    min_len, max_len = (3, 6) if act == "laundry" else (2, 5) if act == "spray" else (1, 3)
    wins = E.best_windows(s, act, a, b, min_len, max_len, k=2)
    if not wins and (b - a) <= 24:
        wins = E.best_windows(s, act, a, min(s.n, b + 24), min_len, max_len, k=2, min_score=50)
    blocks = []
    if not wins:
        bad = E.bad_spans(s, act, a, b)
        txt = f"I couldn't find a comfortable time for {lab} {when['label']}."
        if bad:
            txt += f" The main problem is {bad[0]['issue']} around {bad[0]['range']}."
        txt += " Try another day, or ask me to check tomorrow."
        return txt, blocks, s.conf(a)
    w = wins[0]
    txt = f"The best time for {lab} is **{w['day']} {w['range']}**."
    if w["why"]:
        txt += " " + cap1("; ".join(w["why"][:4])) + "."
    now_sc = E.score_hour(act, s, s.i0)
    if re.search(r"should i|can i|is it (ok|okay|good|fine|safe)", text.lower()) and when["day_offset"] == 0:
        if now_sc >= 70:
            txt = f"Yes — conditions are good for {lab} right now. " + txt
        elif w["day"] == "Today" and w["start_i"] > s.i0:
            txt = f"Not right now ({E.main_issue(s, s.i0)}), but it improves later. " + txt
    blocks.append({"type": "window", "act": lab, "window": w, "alternatives": wins[1:]})
    bad = E.bad_spans(s, act, a, min(b, a + 30))
    if bad:
        blocks.append({"type": "avoid", "items": bad})
        txt += f" Avoid {bad[0]['range']} ({bad[0]['issue']})."
    return txt, blocks, w["confidence"]


def _rain_answer(s, when, text):
    a, b = when["a"], when["b"]
    ro = E.rain_outlook(s, a, b)
    sent = E.rain_sentence(s, a, b, when["label"])
    umb = ""
    if ro["spans"]:
        umb = " Yes, carry an umbrella" + (" or raincoat" if ro["peak"] >= 2.5 else "") + "."
    elif ro["chance"]:
        umb = " A small foldable umbrella is a safe bet."
    else:
        umb = " You can leave the umbrella at home."
    txt = sent + umb
    if any(is_th(s, i) for i in range(a, b)):
        txt += " Thunder is possible, so avoid open ground during the storm."
    return txt, [_strip_block(s, a, b)], s.conf(a)


def _vis_answer(s, when):
    idx = list(range(when["a"], min(s.n, max(when["b"], when["a"] + 1))))
    low = min(idx, key=lambda i: s.vis(i))
    km = round(s.vis(low) / 1000, 1)
    if km >= 8:
        return f"Visibility is good — at least {km} km {when['label']}. No fog concerns.", [], s.conf(when["a"])
    return (f"Visibility drops to about {km} km around {s.label(low)}. Drive slowly with low-beam lights and allow extra time."), [], s.conf(when["a"])


def _summary_answer(s, when):
    a, b = when["a"], max(when["b"], when["a"] + 1)
    idx = list(range(a, min(s.n, b)))
    temps = [s.temp(i) for i in idx]
    code = max((s.code(i) for i in idx), default=0)
    text, emoji = describe(code, True)
    line = f"{cap1(when['label'])}: {emoji} {text}, {round(min(temps))}–{round(max(temps))}°C (feels up to {round(max(s.feels(i) for i in idx))}°C). " + E.rain_sentence(s, a, b, when["label"])
    return line, [_strip_block(s, a, b, 14)], s.conf(a)


def _irrigate_answer(s, profile):
    adv = advisory.farmer(s, profile)
    note = next((c for c in adv[2] if c.get("title") == "Irrigation"), None)
    return (note["text"] if note else "I couldn't work out irrigation right now."), [], "medium"


def is_th(s, i):
    from .wxcodes import is_thunder
    return is_thunder(s.code(i))


def _wear_answer(s, when):
    a, b = when["a"], max(when["b"], when["a"] + 6)
    idx = range(a, min(s.n, b))
    tmax = max(s.feels(i) for i in idx)
    tmin = min(s.feels(i) for i in idx)
    items = []
    if tmax >= 35:
        items.append(("👕", "Light cotton, loose clothes", f"Feels up to {round(tmax)}°C"))
    elif tmax >= 26:
        items.append(("👕", "Light, breathable clothes", f"{round(tmin)}–{round(tmax)}°C"))
    elif tmax >= 18:
        items.append(("👔", "Full sleeves or a light layer", f"{round(tmin)}–{round(tmax)}°C"))
    else:
        items.append(("🧥", "A warm jacket", f"Only {round(tmin)}–{round(tmax)}°C"))
    if tmin <= 20 and tmax >= 26:
        items.append(("🧣", "A light layer for cooler hours", ""))
    if any(s.wet(i) for i in idx):
        items.append(("☂️" if max(s.precip(i) for i in idx) < 2.5 else "🧥", "Umbrella or raincoat", "Rain expected"))
        items.append(("👟", "Shoes that handle wet roads", ""))
    if any(s.uv(i) >= 6 for i in idx):
        items.append(("🧴", "Sunscreen + cap or sunglasses", f"UV {uv_band(max(s.uv(i) for i in idx))}"))
    if tmax >= 32:
        items.append(("💧", "Water bottle", ""))
    if s.aqi and s.aqi > 150:
        items.append(("😷", "Mask", f"AQI {round(s.aqi)}"))
    txt = f"For {when['label']}: " + ", ".join(i[1].lower() for i in items[:3]) + "."
    return txt, [{"type": "checklist", "title": "What to wear & carry", "items": [{"icon": i, "text": t, "sub": sub} for i, t, sub in items]}], s.conf(a)


def _temp_answer(s, when):
    a, b = when["a"], when["b"]
    idx = list(range(a, min(s.n, max(b, a + 1))))
    hot = max(idx, key=lambda i: s.feels(i))
    cool = min(idx, key=lambda i: s.feels(i))
    txt = f"{when['label'].capitalize()}: {round(min(s.temp(i) for i in idx))}–{round(max(s.temp(i) for i in idx))}°C. "
    txt += f"Hottest around {s.label(hot)} (feels like {round(s.feels(hot))}°C), coolest around {s.label(cool)} ({round(s.feels(cool))}°C)."
    if s.feels(hot) >= 38:
        txt += " Do outdoor things in the cooler hours and drink plenty of water."
    return txt, [_strip_block(s, a, b, 14)], s.conf(a)


def _wind_answer(s, when):
    a, b = when["a"], when["b"]
    idx = list(range(a, min(s.n, max(b, a + 1))))
    w = round(max(s.wind(i) for i in idx))
    g = round(max(s.gust(i) for i in idx))
    peak = max(idx, key=lambda i: s.gust(i))
    txt = f"Wind {when['label']}: {wind_words(w)} — up to {w} km/h, gusts to {g} km/h around {s.label(peak)}."
    if g >= 45:
        txt += " Riding a two-wheeler or carrying an umbrella will be difficult."
    elif g < 20:
        txt += " Nothing to worry about."
    return txt, [], s.conf(a)


def _air_answer(s):
    if s.aqi is None:
        return "I couldn't get air-quality data for this place right now.", [], "low"
    b = aqi_band(s.aqi)
    txt = f"Air quality is **{b['label'].lower()}** (US AQI {round(s.aqi)}" + (f", PM2.5 about {round(float(s.pm25))} µg/m³" if s.pm25 else "") + f"). {b['advice']}"
    return txt, [], "high"


def _uv_answer(s, when):
    idx = list(range(when["a"], min(s.n, max(when["b"], when["a"] + 1))))
    peak = max(idx, key=lambda i: s.uv(i))
    u = round(s.uv(peak), 1)
    txt = f"UV peaks at {u} ({uv_band(u)}) around {s.label(peak)}."
    txt += " Use sunscreen and avoid direct sun 11 AM–3 PM." if u >= 6 else " Normal sun care is enough."
    return txt, [], s.conf(when["a"])


def _plan_answer(s, text):
    t = text.lower()
    if re.search(r"3 days|three days|next \d+ days|this week|weekend", t):
        days = E.daily_list(s)[:4]
        txt = "Here's your outlook: " + "; ".join(f"{d['label']} {d['emoji']} {d['hi']}°/{d['lo']}° ({d['pop']}% rain)" for d in days) + "."
        return txt, [{"type": "days", "days": days}], "medium"
    plan = E.day_plan(s, 0)
    if len(plan) < 2:
        plan = plan + E.day_plan(s, 1)
    risks = E.compound_risks(s)
    bw = E.best_windows(s, "outdoor", s.i0, min(s.n, s.i0 + 30), 1, 3, k=1)
    txt = "Here's how your day looks: " + " ".join(f"**{p['label']}** — {p['title'].lower()}." for p in plan[:4])
    if bw:
        txt += f" Best outdoor window: **{bw[0]['day']} {bw[0]['range']}**."
    blocks = [{"type": "plan", "items": plan}]
    if risks:
        blocks.append({"type": "risks", "items": risks[:3]})
    return txt, blocks, s.conf(s.i0 + 3)


def _whatif_answer(s, text, act):
    t = text.lower()
    hours = []
    for m in re.finditer(r"(\d{1,2})(?::\d{2})?\s*(am|pm)?", t):
        h = int(m.group(1))
        if not (0 <= h <= 24):
            continue
        if m.group(2):
            h = h % 12 + (12 if m.group(2) == "pm" else 0)
        elif 1 <= h <= 6:
            h += 12
        if re.match(r"\d{1,2}\s*(km|mm|c\b|%)", t[m.start():m.start() + 6]) or h > 23:
            continue
        hours.append(h)
    day_offset = 1 if re.search(r"tomorrow|\btom\b", t) else 0
    date = (s.now_dt.date() + timedelta(days=day_offset)).isoformat()
    m2 = re.search(r"(\d+)\s*(?:hour|hr|h)s?\s*(later|earlier)", t)
    if len(hours) >= 2:
        i1, i2 = s.idx(date, hours[0]), s.idx(date, hours[1])
    else:
        base = hours[0] if hours else (s.now_dt.hour + 1)
        shift = int(m2.group(1)) if m2 else 1
        if m2 and m2.group(2) == "earlier":
            shift = -shift
        i1, i2 = s.idx(date, base % 24), s.idx(date, (base + shift) % 24)
    if i1 is None or i2 is None:
        return "I couldn't line up those two times in the forecast — try something like \"what if I leave at 5 PM instead of 6 PM?\"", [], "low"
    i1, i2 = max(i1, s.i0), max(i2, s.i0)
    w = E.what_if(s, i1, i2, act or "commute")
    return w["verdict"], [{"type": "compare", "compare": w}], s.conf(min(i1, i2))


async def _alerts_answer(lat, lon, name):
    res = await alerts_engine.all_alerts(lat, lon)
    near = [a for a in res["alerts"] if a["near"]][:3]
    other = [a for a in res["alerts"] if not a["near"]][:2]
    if near:
        txt = f"There {'is' if len(near) == 1 else 'are'} **{len(near)} alert{'s' if len(near) != 1 else ''} near {name}**: " + "; ".join(a["title"] for a in near) + "."
    elif other:
        txt = f"Nothing significant near {name}. Elsewhere in India: " + "; ".join(a["title"] for a in other) + "."
    else:
        txt = f"No weather alerts near {name} or elsewhere right now."
    txt += " (Forecast-based — check IMD/NDMA for official warnings.)"
    return txt, [{"type": "alerts", "items": (near or other)[:3]}] if (near or other) else [], "medium"


async def _route_answer(text, places, default, depart_hour):
    if len(places) >= 2:
        a, b = places[0], places[1]
    else:
        a, b = default, places[0] if places else None
    if not b:
        return "Tell me where you're going, for example: \"Bengaluru to Chennai at 8 AM\".", [], "low"
    now = __import__("app.services.mockdata", fromlist=["now_local"]).now_local() if om.is_mock() else None
    from datetime import datetime, timedelta as td
    base = now or datetime.now()
    hour = depart_hour if depart_hour is not None else base.hour + 1
    dep = base.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    if dep < base - td(minutes=30):
        dep += td(days=1)
    if re.search(r"tomorrow|\btom\b", text.lower()) and dep.date() == base.date():
        dep += td(days=1)
    plan = await routeeng.plan((a["lat"], a["lon"]), (b["lat"], b["lon"]), a["name"], b["name"], dep)
    v = plan["verdict"]
    txt = f"{a['name']} → {b['name']}: about {plan['distance_km']} km, {plan['duration_text']}. **{v['headline']}.** {v['detail']} {plan['suggestion']}".strip()
    return txt, [{"type": "route", "route": plan}], "medium"


async def _sea_answer(lat, lon, name, persona_profile):
    s = await snapshot.load(lat, lon, name, marine=True)
    adv = advisory.fisherman(s, persona_profile)
    v = adv[0]
    return f"**{v['headline']}.** {v['detail']}", [{"type": "advice", "advice": {"verdict": v, "cards": adv[2][:2]}}], "medium", s


def _general_facts(s, br):
    return json.dumps({"place": s.name, "now": br["now"], "headline": br["headline"], "plan": [{"part": p["label"], "summary": p["title"], "detail": p["detail"]} for p in br["plan"]],
                       "risks": [r["title"] for r in br["risks"]], "best_outdoor_window": (br["best_window"] or {}).get("range"), "aqi": br["aqi"],
                       "next_days": br["daily"][:4]}, default=str)


# ------------------------------------------------------------------ main
async def respond(text, lat, lon, place_name=None, persona="office", profile=None, language="en"):
    profile = profile or {}
    raw_text = text.strip()
    q = raw_text
    lang_code = (language or "en").split("-")[0].lower()
    non_latin = bool(re.search(r"[^\x00-\x7F]", raw_text)) and len(re.findall(r"[A-Za-z]", raw_text)) < len(raw_text) / 3
    note = None
    if non_latin or lang_code != "en":
        if non_latin:
            if G.available():
                try:
                    q = G.to_english(raw_text)
                except Exception as e:  # noqa: BLE001
                    log.info("translate-in failed: %s", e)
                    note = "I understood best in English right now — translation isn't available."
            else:
                note = "I can only read English questions for now (translation service isn't set up)."
    t = q.lower()

    act = detect_activity(t)
    places = await find_places(q)
    default = {"name": place_name or snapshot.resolve_name(lat, lon), "lat": lat, "lon": lon}
    main = places[0] if (places and detect_intent(t, act, places) != "route") else default
    intent = detect_intent(t, act, places)

    facts_place = main
    blocks, conf, s = [], "medium", None
    if intent == "route":
        depart_h = parse_hour(t)
        txt, blocks, conf = await _route_answer(q, places, default, depart_h)
        s = await snapshot.load(default["lat"], default["lon"], default["name"], past_days=1, forecast_days=3)
    elif intent == "alerts":
        txt, blocks, conf = await _alerts_answer(main["lat"], main["lon"], main["name"])
        s = await snapshot.load(main["lat"], main["lon"], main["name"], past_days=1, forecast_days=3)
    elif intent == "sea":
        txt, blocks, conf, s = await _sea_answer(main["lat"], main["lon"], main["name"], profile)
    else:
        s = await snapshot.load(main["lat"], main["lon"], main["name"], past_days=1, forecast_days=7)
        when = resolve_when(q, s)
        am, pm = int(profile.get("am", 9)), int(profile.get("pm", 18))
        cw = None
        if re.search(r"head(ing)? home|go(ing)? home|leave (the )?office|leaving (the )?office|after work|way home|return trip|coming back|come back home", t):
            cw = ("evening", pm)
        elif re.search(r"go(ing)? to (the )?(office|work|school|college)|leave (for|to) (the )?(office|work|school|college)|morning commute|reach (the )?office|head(ing)? to (the )?(office|work)", t):
            cw = ("morning", am)
        if cw and not when["explicit"] or (cw and when["day_offset"] in (0, 1) and when["hour"] is None and not re.search(r"morning|afternoon|evening|night", t.replace("morning commute", ""))):
            for off in (0, 1):
                i = s.idx((s.now_dt.date() + timedelta(days=off)).isoformat(), cw[1])
                if i is not None and i >= s.i0 and (off == when["day_offset"] or not when["explicit"]):
                    when = {"a": i, "b": min(s.n, i + 2), "label": f"during your usual {cw[0]} commute ({s.label(i)}, {s.day_name(i).lower()})", "day_offset": off, "hour": cw[1], "explicit": True}
                    break
        if intent == "window":
            txt, blocks, conf = _window_answer(s, act or "outdoor", when, q)
        elif intent == "rain":
            txt, blocks, conf = _rain_answer(s, when, q)
        elif intent == "wear":
            txt, blocks, conf = _wear_answer(s, when)
        elif intent == "temp":
            txt, blocks, conf = _temp_answer(s, when)
        elif intent == "wind":
            txt, blocks, conf = _wind_answer(s, when)
        elif intent == "air":
            txt, blocks, conf = _air_answer(s)
        elif intent == "uv":
            txt, blocks, conf = _uv_answer(s, when)
        elif intent == "vis":
            txt, blocks, conf = _vis_answer(s, when)
        elif intent == "summary":
            txt, blocks, conf = _summary_answer(s, when)
        elif intent == "irrigate":
            txt, blocks, conf = _irrigate_answer(s, profile)
        elif intent == "plan":
            txt, blocks, conf = _plan_answer(s, q)
        elif intent == "whatif":
            txt, blocks, conf = _whatif_answer(s, q, act)
        else:
            br = E.briefing(s, profile, None, persona)
            txt = " ".join(br["sentences"][:3])
            if G.available():
                try:
                    txt = G.grounded_answer(q, _general_facts(s, br), persona)
                except Exception as e:  # noqa: BLE001
                    log.info("grounded answer failed: %s", e)
            else:
                txt += "\n\nTry asking things like “best time for a run tomorrow”, “will it rain when I leave office?”, “Bengaluru to Chennai at 8 AM” or “what if I leave at 5 instead of 6?”."
            blocks = [{"type": "plan", "items": br["plan"]}]

    # location note when answering about a different place than the user's own
    loc_note = None
    if intent not in ("route",) and main is not default and main["name"] != default["name"]:
        loc_note = main["name"]

    if note:
        txt = txt + "\n\n_" + note + "_"
    answer_lang = None
    if lang_code != "en" and lang_code in LANGS and G.available():
        try:
            txt = G.from_english(txt, LANGS[lang_code])
            answer_lang = lang_code
        except Exception as e:  # noqa: BLE001
            log.info("translate-out failed: %s", e)

    br_sugg = E.suggestions(s, persona, profile, E.compound_risks(s)) if s else []
    follow = []
    if intent == "window":
        follow += [{"q": "What if I go 1 hour later?", "kind": "tip"}, {"q": "When is the worst time to go out today?", "kind": "tip"}]
    if intent == "rain":
        follow += [{"q": "Will it rain tomorrow?", "kind": "tip"}, {"q": "Plan my day", "kind": "tip"}]
    if intent == "route":
        follow += [{"q": "What if I leave 1 hour later?", "kind": "tip"}]
    sugg = (follow + br_sugg)[:6]
    theme = E.sky_block(s)["theme"] if s else "clear-day"
    return {
        "answer": txt, "blocks": blocks, "suggestions": sugg, "confidence": conf, "language": answer_lang or "en", "theme": theme,
        "location_name": (main["name"] if main else None), "intent": intent, "activity": act, "location_note": loc_note,
        "source": "demo" if om.is_mock() else "live", "sky": E.sky_block(s) if s else None,
    }
