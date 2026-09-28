"""
Persona advisories. Each persona gets its own verdict, key numbers, hour-by-hour
strip and cards built from the same real forecast — different people, different
questions ("Will my commute be wet?" vs "Can I spray today?" vs "Is the sea safe?").
"""
from datetime import timedelta

from . import cities, engine as E
from .wxcodes import aqi_band, describe, is_thunder, uv_band, wind_words

PERSONAS = {
    "office": {"name": "Office worker", "emoji": "💼", "tag": "Commute & workday", "act": "commute"},
    "student": {"name": "Student", "emoji": "🎒", "tag": "School / college run", "act": "commute"},
    "commuter": {"name": "Two-wheeler rider", "emoji": "🏍️", "tag": "Roads & riding", "act": "riding"},
    "delivery": {"name": "Delivery rider", "emoji": "📦", "tag": "Shift planning", "act": "riding"},
    "fitness": {"name": "Runner / Cyclist", "emoji": "🏃", "tag": "Best workout windows", "act": "running"},
    "parent": {"name": "Parent", "emoji": "👨‍👩‍👧", "tag": "Kids & school", "act": "kids"},
    "traveler": {"name": "Traveller", "emoji": "🧳", "tag": "Next few days", "act": "outdoor"},
    "farmer": {"name": "Farmer", "emoji": "🌾", "tag": "Fields & crops", "act": "field"},
    "fisherman": {"name": "Fisherman", "emoji": "🐟", "tag": "Sea conditions", "act": "outdoor"},
    "aviation": {"name": "Aviation", "emoji": "✈️", "tag": "Flight briefing", "act": "flying"},
}
VERDICT = {"good": ("Good to go", "🟢"), "ok": ("Fine, with small tweaks", "🟡"), "caution": ("Be careful", "🟠"), "avoid": ("Plan around it", "🔴")}
LEVEL = {"good": 0, "ok": 1, "caution": 2, "avoid": 3}
FROM_LEVEL = ["good", "ok", "caution", "avoid"]


def _verdict(level, headline, detail=""):
    label, emoji = VERDICT[level]
    return {"level": level, "label": label, "emoji": emoji, "headline": headline, "detail": detail}


def _tone_to_level(tone):
    return {"good": "good", "ok": "ok", "caution": "caution", "warn": "avoid"}[tone]


def _next_idx(s, hour):
    for off in (0, 1, 2):
        date = (s.now_dt.date() + timedelta(days=off)).isoformat()
        i = s.idx(date, hour)
        if i is not None and i >= s.i0:
            return i
    return None


def _stat(icon, label, value, sub=""):
    return {"icon": icon, "label": label, "value": value, "sub": sub}


def _carry(s, a, b, light_wind=False):
    items = []
    idx = range(max(0, a), min(s.n, b))
    if any(is_thunder(s.code(i)) for i in idx) or any(s.precip(i) >= 2.5 for i in idx):
        items.append(("🧥", "Raincoat or poncho", "Steady rain expected"))
    elif any(s.wet(i) or s.pop(i) >= 40 for i in idx):
        items.append(("☂️", "Umbrella", "Rain chance during this time"))
    if any(s.feels(i) >= 35 for i in idx):
        items.append(("💧", "Water bottle", f"Feels like {round(max(s.feels(i) for i in idx))}°C"))
    if any(s.uv(i) >= 6 for i in idx):
        items.append(("🧴", "Sunscreen + cap", f"UV {uv_band(max(s.uv(i) for i in idx))}"))
    if s.aqi and s.aqi > 150:
        items.append(("😷", "Mask", f"AQI {round(s.aqi)}"))
    if any(s.temp(i) <= 14 for i in idx):
        items.append(("🧣", "A warm layer", "It turns cool"))
    if any(s.gust(i) >= 40 for i in idx) and not light_wind:
        items.append(("🧢", "Something wind-proof", "Gusty"))
    return items


def _strip(s, act, n=18):
    return E.hourly_strip(s, s.i0, n, act)


def _commute_card(s, word, hour, mode):
    t = _next_idx(s, hour)
    if t is None:
        return None, None
    span = [t, t + 1]
    sc = min(E.score_hour(mode, s, j) for j in span)
    # best departure within +-2h
    best, best_sc = t, sc
    for c in (t - 2, t - 1, t + 1, t + 2):
        if c < s.i0 or c + 1 >= s.n:
            continue
        v = min(E.score_hour(mode, s, j) for j in (c, c + 1)) - abs(c - t) * 3
        if v > best_sc + 5:
            best, best_sc = c, v
    tone = E.tone_for(sc)
    issue = E.main_issue(s, next((j for j in span if E.score_hour(mode, s, j) == sc), t))
    text, emoji = describe(s.code(t), s.is_day(t))
    if tone == "good":
        headline = "Dry and easy"
    elif tone == "ok":
        headline = "Mostly fine"
    else:
        headline = f"Watch out: {issue}"
    tip = ""
    if best != t and tone != "good":
        tip = f"Leaving around {s.label(best)} instead gives a smoother trip (rain chance {int(s.pop(t))}% → {int(s.pop(best))}%)."
    elif tone == "good":
        tip = "No change needed."
    card = {"type": "commute", "title": f"{word.title()} · {s.day_name(t)} {s.label(t)}", "tone": tone, "emoji": emoji, "headline": headline,
            "metrics": [f"{round(s.temp(t))}°C", f"{int(max(s.pop(j) for j in span))}% rain", f"{round(max(s.gust(j) for j in span))} km/h gusts"],
            "tip": tip, "text": text}
    return card, sc


def _why(facts, analysis, suggestion):
    return {"facts": facts, "analysis": analysis, "suggestion": suggestion}


def _dos_from(s, a, b, act):
    dos, donts = [], []
    idx = range(max(0, a), min(s.n, b))
    if any(s.wet(i) for i in idx):
        dos.append("Keep rain gear within reach")
        donts.append("Don't park or walk through flooded low patches")
    if any(s.feels(i) >= 38 for i in idx):
        dos.append("Sip water through the day")
        donts.append("Avoid hard outdoor effort at 12–4 PM")
    if any(is_thunder(s.code(i)) for i in idx):
        donts.append("Don't shelter under trees or stand in open ground during lightning")
    if s.aqi and s.aqi > 150:
        dos.append("Wear a mask outdoors; keep windows closed")
    if not dos:
        dos.append("Go ahead with your normal plans")
    return dos[:4], donts[:3]


# ------------------------------------------------------------------ personas
def _office_like(persona, s, profile, mode, am, pm, label_am, label_pm):
    cards, levels, scores = [], [], []
    for word, hour in ((label_am, am), (label_pm, pm)):
        c, sc = _commute_card(s, word, hour, mode)
        if c:
            cards.append(c)
            levels.append(LEVEL[_tone_to_level(c["tone"])])
    worst = max(levels) if levels else 0
    lvl = FROM_LEVEL[worst]
    t_am = _next_idx(s, am)
    t_pm = _next_idx(s, pm)
    targets = [x for x in (t_am, t_pm) if x is not None]
    span_a = min(targets) if targets else s.i0
    span_b = (max(targets) + 2) if targets else s.i0 + 12
    carry = _carry(s, min(span_a, s.i0 + 1), span_b)
    if carry:
        cards.append({"type": "checklist", "title": "Carry with you", "items": [{"icon": i, "text": t, "sub": sub} for i, t, sub in carry]})
    lunch = next((i for i in range(s.i0, min(s.n, s.i0 + 30)) if s.dt(i).hour == 13 and i >= s.i0), None)
    if lunch is not None and persona == "office":
        sc = E.score_hour("walking", s, lunch)
        cards.append({"type": "note", "title": "Lunch break", "tone": E.tone_for(sc),
                      "text": ("A short lunch walk should be pleasant." if sc >= 70 else f"Better to eat in — {E.main_issue(s, lunch)} around 1 PM.")})
    if persona == "student":
        pe = _next_idx(s, 11)
        if pe is not None:
            sc = E.score_hour("outdoor", s, pe)
            cards.append({"type": "note", "title": "Outdoor games / PT period (11 AM–12 PM)", "tone": E.tone_for(sc),
                          "text": "Fine for outdoor sport." if sc >= 70 else f"Outdoor activity is not ideal ({E.main_issue(s, pe)}); water breaks or an indoor plan help."})
    head = {"good": "Dry, comfortable commute both ways", "ok": "Mostly fine — small adjustments help",
            "caution": "Part of your commute is affected by weather", "avoid": "Rough conditions on your commute"}[lvl]
    detail = " ".join(n["text"] for n in E.commute_notes(s, {"am": am, "pm": pm}))
    dos, donts = _dos_from(s, span_a, span_b, mode)
    facts = [f"{c['title']}: {', '.join(c['metrics'])}" for c in cards if c["type"] == "commute"]
    tips = [c["tip"] for c in cards if c["type"] == "commute" and c["tip"] and c["tip"] != "No change needed."]
    why = _why(facts, {"good": "Nothing in the forecast clashes with your travel times.", "ok": "One or two hours are a little off but nothing serious.",
                       "caution": "Weather overlaps with at least one of your trips.", "avoid": "Conditions on your route are poor."}[lvl],
               tips[0] if tips else "Travel at your usual times.")
    stats = []
    if t_am is not None:
        stats.append(_stat("🌡️", "Morning", f"{round(s.temp(t_am))}°C", f"feels {round(s.feels(t_am))}°C"))
    if t_pm is not None:
        stats.append(_stat("🌇", "Evening", f"{round(s.temp(t_pm))}°C", f"{int(s.pop(t_pm))}% rain chance"))
    stats.append(_stat("💨", "Gusts", f"{round(max(s.gust(i) for i in range(span_a, min(s.n, span_b))))} km/h", "during commute"))
    if s.aqi is not None:
        b = aqi_band(s.aqi)
        stats.append(_stat("😷", "Air", f"AQI {round(s.aqi)}", b["label"]))
    return _verdict(lvl, head, detail), stats, cards, dos, donts, why, {"commute_hours": [t_am, t_pm]}


def office(s, profile):
    am, pm = int(profile.get("am", 9)), int(profile.get("pm", 18))
    return _office_like("office", s, profile, "commute", am, pm, "Morning commute", "Evening commute")


def student(s, profile):
    return _office_like("student", s, profile, "commute", 8, 16, "Going to school/college", "Coming back")


def commuter(s, profile):
    am, pm = int(profile.get("am", 9)), int(profile.get("pm", 18))
    v, stats, cards, dos, donts, why, ex = _office_like("commuter", s, profile, "riding", am, pm, "Morning ride", "Evening ride")
    recent = sum(s.precip(i) for i in range(max(0, s.i0 - 4), s.i0 + 1))
    dry_before = sum(s.precip(i) for i in range(max(0, s.i0 - 30), max(0, s.i0 - 6))) < 0.5
    if recent >= 0.3:
        cards.insert(0, {"type": "note", "title": "Roads may still be slippery", "tone": "caution",
                         "text": "It rained in the last few hours — brake early and avoid painted lines and manhole covers."
                                 + (" First rain after a dry spell makes roads extra oily." if dry_before else "")})
    if any(s.gust(i) >= 40 for i in range(s.i0, s.i0 + 12)):
        donts.append("Avoid flyovers and open bridges when gusts are strong")
    if any(s.vis(i) < 1500 for i in range(s.i0, s.i0 + 12)):
        dos.append("Use low-beam lights; keep extra distance")
    return v, stats, cards, dos[:4], donts[:3], why, ex


def delivery(s, profile):
    a = s.i0
    b = next((i for i in range(a, min(s.n, a + 30)) if s.dt(i).hour == 22 and i > a), min(s.n, a + 12))
    if b - a < 3:
        a, b = s.i0, min(s.n, s.i0 + 12)
    scores = [E.score_hour("riding", s, i) for i in range(a, b)]
    bad = sum(1 for x in scores if x < 40)
    share = bad / max(1, len(scores))
    lvl = "avoid" if share > 0.5 else "caution" if share > 0.25 else "ok" if share > 0.08 else "good"
    rough = E.bad_spans(s, "riding", a, b, thresh=45)
    best = E.best_windows(s, "riding", a, b, 2, 5, k=2, min_score=60)
    cards = []
    if rough:
        cards.append({"type": "list", "title": "Rough patches on your shift", "tone": "caution",
                      "items": [{"icon": "⚠️", "text": f"{r['range']}", "sub": r["issue"]} for r in rough]})
    else:
        cards.append({"type": "note", "title": "Rough patches", "tone": "good", "text": "No major weather trouble expected during the rest of today's shift."})
    if best:
        cards.append({"type": "windows", "title": "Smoothest riding hours", "windows": best[:2]})
    heat = [i for i in range(a, b) if s.feels(i) >= 38]
    if heat:
        sp = E._spans(heat)[0]
        cards.append({"type": "note", "title": "Heat break reminder", "tone": "caution",
                      "text": f"Feels like {round(max(s.feels(i) for i in heat))}°C between {s.label(sp[0])} and {s.label(sp[1] + 1)}. A shade + water break every 45–60 minutes protects you from heat exhaustion."})
    carry = _carry(s, a, b)
    if carry:
        cards.append({"type": "checklist", "title": "Gear for today", "items": [{"icon": i, "text": t, "sub": sub} for i, t, sub in carry]})
    wet_hours = sum(1 for i in range(a, b) if s.wet(i))
    head = {"good": "A smooth day on the road", "ok": "Mostly smooth, a few damp hours", "caution": "Expect some rough hours",
            "avoid": "Tough day — weather hits much of your shift"}[lvl]
    detail = f"{wet_hours} wet hour{'s' if wet_hours != 1 else ''} and {bad} rough hour{'s' if bad != 1 else ''} in the rest of your shift."
    stats = [_stat("🌧️", "Wet hours", str(wet_hours), "rest of shift"), _stat("🥵", "Peak feels-like", f"{round(max(s.feels(i) for i in range(a, b)))}°C"),
             _stat("💨", "Max gust", f"{round(max(s.gust(i) for i in range(a, b)))} km/h")]
    if s.aqi is not None:
        stats.append(_stat("😷", "Air", f"AQI {round(s.aqi)}", aqi_band(s.aqi)["label"]))
    dos, donts = _dos_from(s, a, b, "riding")
    donts.append("Don't rush orders on wet roads — late is better than a fall")
    why = _why([f"{wet_hours} wet hours, {bad} rough hours", f"Feels like up to {round(max(s.feels(i) for i in range(a, b)))}°C"],
               "Rain and gusts make roads slower and riskier; heat drains energy.", (best[0]["range"] + " looks like your smoothest stretch.") if best else "Keep gear handy and take breaks.")
    return _verdict(lvl, head, detail), stats, cards, dos[:4], donts[:3], why, {}


def fitness(s, profile):
    fav = profile.get("fav") if profile.get("fav") in ("running", "cycling", "walking") else None
    acts = [fav] if fav else ["running", "cycling"]
    cards, best_all = [], []
    for act in acts:
        w = E.best_windows(s, act, s.i0, min(s.n, s.i0 + 36), 1, 3, k=2)
        if w:
            best_all.append(w[0])
            cards.append({"type": "windows", "title": f"Best time for {E.act_label(act)}", "windows": w})
        else:
            cards.append({"type": "note", "title": f"Best time for {E.act_label(act)}", "tone": "caution", "text": "No comfortable window in the next 36 hours — try an indoor session."})
    avoid = E.bad_spans(s, "running", s.i0, min(s.n, s.i0 + 24), thresh=40)
    if avoid:
        cards.append({"type": "list", "title": "Skip these hours", "tone": "caution", "items": [{"icon": "⛔", "text": a["range"], "sub": a["issue"]} for a in avoid]})
    lvl = "good"
    if best_all:
        top = max(best_all, key=lambda w: w["score"])
        lvl = _tone_to_level(E.tone_for(top["score"]))
        head = f"Best window: {top['day']} {top['range']}"
        detail = "; ".join(top["why"][:3])
    else:
        lvl, head, detail = "caution", "No good outdoor window soon", "Consider a treadmill, yoga or a home workout."
    stats = [_stat("🌡️", "Feels like now", f"{E.now_block(s)['feels']}°C"), _stat("☀️", "UV today", f"{round(max(s.uv(i) for i in range(s.i0, min(s.n, s.i0 + 14))), 1)}", uv_band(max(s.uv(i) for i in range(s.i0, min(s.n, s.i0 + 14)))) or "")]
    if s.aqi is not None:
        stats.append(_stat("😷", "Air", f"AQI {round(s.aqi)}", aqi_band(s.aqi)["label"]))
    stats.append(_stat("💧", "Humidity", f"{E.now_block(s)['humidity']}%"))
    dos = ["Warm up 5 minutes before you start", "Carry water if you'll be out over 30 minutes"]
    donts = ["Don't push hard when feels-like is above 35°C"]
    if s.aqi and s.aqi > 100:
        donts.append("Skip long outdoor sessions when AQI is above 100")
    why = _why([f"Top window scored {best_all[0]['score']}/100" if best_all else "No hour scored above 55/100"],
               "Scores combine temperature, rain chance, wind, sun (UV), visibility and air quality.",
               (best_all[0]["why"][0].capitalize() + " during the best window.") if best_all else "Pick an indoor option today.")
    return _verdict(lvl, head, detail), stats, cards, dos, donts, why, {}


def parent(s, profile):
    cards = []
    kids = E.best_windows(s, "kids", s.i0, min(s.n, s.i0 + 36), 1, 2, k=2)
    if kids:
        cards.append({"type": "windows", "title": "Good hours for kids to play outside", "windows": kids})
    else:
        cards.append({"type": "note", "title": "Outdoor play", "tone": "caution", "text": "No comfortable outdoor slot soon — plan indoor games."})
    for word, hour in (("School drop-off", 8), ("Pick-up", 15)):
        c, _ = _commute_card(s, word, hour, "kids")
        if c:
            cards.append(c)
    dress = []
    hi = max(s.temp(i) for i in range(s.i0, min(s.n, s.i0 + 14)))
    uvm = max(s.uv(i) for i in range(s.i0, min(s.n, s.i0 + 14)))
    if hi >= 33:
        dress.append(("👕", "Light cotton clothes", f"High of {round(hi)}°C"))
    if uvm >= 6:
        dress.append(("🧢", "Cap + sunscreen", f"UV {uv_band(uvm)}"))
    if any(s.wet(i) for i in range(s.i0, min(s.n, s.i0 + 14))):
        dress.append(("🧥", "Raincoat + spare socks", "Rain expected"))
    if any(s.temp(i) <= 16 for i in range(s.i0, min(s.n, s.i0 + 14))):
        dress.append(("🧦", "A light jacket", "Cool hours"))
    dress.append(("💧", "Water bottle", "Always"))
    cards.append({"type": "checklist", "title": "What kids should wear / carry", "items": [{"icon": i, "text": t, "sub": sub} for i, t, sub in dress]})
    if s.aqi and s.aqi > 100:
        cards.append({"type": "note", "title": "Air quality", "tone": "caution", "text": aqi_band(s.aqi)["advice"] + " Keep outdoor play short."})
    lvl = "good"
    if kids:
        lvl = _tone_to_level(E.tone_for(kids[0]["score"]))
        head = f"Best outdoor play: {kids[0]['day']} {kids[0]['range']}"
        detail = "; ".join(kids[0]["why"][:3])
    else:
        lvl, head, detail = "caution", "Mostly indoor day", "Weather isn't kid-friendly for the next day or so."
    stats = [_stat("☀️", "UV peak", f"{round(uvm, 1)}", uv_band(uvm) or ""), _stat("🌡️", "High today", f"{round(hi)}°C"),
             _stat("🌧️", "Rain chance", f"{int(max(s.pop(i) for i in range(s.i0, min(s.n, s.i0 + 14))))}%")]
    if s.aqi is not None:
        stats.append(_stat("😷", "Air", f"AQI {round(s.aqi)}", aqi_band(s.aqi)["label"]))
    dos = ["Play outside in the early morning or late afternoon", "Reapply sunscreen every 2 hours in strong sun"]
    donts = ["Don't keep kids out in the midday sun on hot days", "Avoid open playgrounds during thunder"]
    why = _why([f"UV peaks at {round(uvm, 1)}", f"High of {round(hi)}°C"], "Kids overheat and burn faster than adults.", kids[0]["range"] + " balances temperature, sun and rain best." if kids else "Stay indoors for now.")
    return _verdict(lvl, head, detail), stats, cards, dos, donts, why, {}


def traveler(s, profile):
    days = E.daily_list(s)[:4]
    scored = []
    for d in days:
        sc = 100 - (d["pop"] or 0) * 0.6 - d["rain_mm"] * 3 - max(0, d["hi"] - 34) * 4
        scored.append((sc, d))
    best = max(scored, key=lambda x: x[0])[1] if scored else None
    cards = [{"type": "days", "title": "Next few days", "days": [dict(d, best=(best is d)) for d in days]}]
    risks = E.compound_risks(s, s.i0, min(s.n, s.i0 + 72))
    if risks:
        cards.append({"type": "risks", "title": "Things that could disrupt travel", "risks": risks[:3]})
    pack = [("👕", "Light breathable clothes", "")]
    if any(d["rain_mm"] >= 2 or (d["pop"] or 0) >= 50 for d in days):
        pack.append(("☂️", "Umbrella / raincoat", "Rain on at least one day"))
    if any(d["hi"] >= 34 for d in days):
        pack += [("🧴", "Sunscreen", ""), ("💧", "Reusable water bottle", "Hot days ahead")]
    if any(d["lo"] <= 14 for d in days):
        pack.append(("🧥", "A light jacket", "Cool mornings/evenings"))
    cards.append({"type": "checklist", "title": "Packing", "items": [{"icon": i, "text": t, "sub": sub} for i, t, sub in pack]})
    lvl = "good" if not risks else FROM_LEVEL[min(3, max(r["level"] for r in risks))]
    head = f"Best day for sightseeing: {best['label']} ({best['date_short']})" if best else "Outlook"
    detail = f"{best['emoji']} {best['hi']}°/{best['lo']}° with {best['pop']}% rain chance." if best else ""
    stats = [_stat("🌡️", "Today", f"{days[0]['hi']}°/{days[0]['lo']}°") if days else None,
             _stat("🌧️", "Rainy days", str(sum(1 for d in days if d["rain_mm"] >= 2 or (d["pop"] or 0) >= 50)), "of next 4")]
    stats = [x for x in stats if x]
    if s.aqi is not None:
        stats.append(_stat("😷", "Air", f"AQI {round(s.aqi)}", aqi_band(s.aqi)["label"]))
    why = _why([f"{d['label']}: {d['hi']}°/{d['lo']}°, {d['pop']}% rain" for d in days], "Each day is scored on rain chance, rainfall and heat.",
               f"Put outdoor sightseeing on {best['label']}." if best else "")
    return _verdict("good" if lvl in ("good", "ok") and not risks else lvl, head, detail), stats, cards, ["Check airline/train status on travel day", "Keep a flexible plan for the wettest day"], \
        ["Don't schedule outdoor tours during storm hours"], why, {}


def farmer(s, profile):
    cards = []
    a, b = s.i0, min(s.n, s.i0 + 48)
    spray = E.best_windows(s, "spray", a, b, 2, 5, k=2, min_score=60)
    cards.append({"type": "windows", "title": "Best time to spray", "windows": spray} if spray else
                 {"type": "note", "title": "Best time to spray", "tone": "caution", "text": "No safe spraying window in the next 2 days — rain or wind would wash off or spread the spray."})
    rain24 = round(sum(s.precip(i) for i in range(a, min(s.n, a + 24))), 1)
    rain48 = round(sum(s.precip(i) for i in range(a, b)), 1)
    et48 = round(sum(s.et0(i) for i in range(a, b)), 1)
    soil = s.soil(a)
    soil_word = None if soil is None else ("wet" if soil > 0.35 else "moist" if soil > 0.2 else "dry")
    if rain48 >= 15:
        irr_tone, irr = "good", f"Skip irrigation — about {rain48} mm of rain expected in 48 hours."
    elif rain48 >= 5:
        irr_tone, irr = "ok", f"Light irrigation may still help; only {rain48} mm of rain expected while crops lose about {et48} mm to evaporation."
    else:
        irr_tone, irr = ("caution" if et48 >= 6 and soil_word == "dry" else "ok"), f"Little rain ahead ({rain48} mm) and crops lose about {et48} mm/2 days to evaporation" + (f"; topsoil looks {soil_word}." if soil_word else ".")
    cards.append({"type": "note", "title": "Irrigation", "tone": irr_tone, "text": irr})
    work = E.best_windows(s, "field", a, min(s.n, a + 36), 3, 6, k=1, min_score=60)
    if work:
        cards.append({"type": "windows", "title": "Best hours for field work", "windows": work})
    humid = [i for i in range(a, b) if s.hum(i) >= 85 and 20 <= s.temp(i) <= 30]
    if len(humid) >= 6:
        cards.append({"type": "note", "title": "Crop disease watch", "tone": "caution", "text": f"Warm, very humid air for about {len(humid)} hours favours fungal disease. Check leaves and avoid overhead watering in the evening."})
    if s.wet(a) or any(s.wet(i) for i in range(a, min(s.n, a + 12))):
        cards.append({"type": "note", "title": "Harvest & stored grain", "tone": "caution", "text": "Rain expected within 12 hours — cover harvested produce and stored grain, and harvest ripe crop earlier if you can."})
    cards.append({"type": "rainbars", "title": "Rain expected", "items": [{"label": "Next 24 h", "mm": rain24}, {"label": "Next 48 h", "mm": rain48}]})
    heat = any(s.feels(i) >= 40 for i in range(a, min(s.n, a + 14)))
    if rain24 >= 35:
        lvl, head = "caution", "Heavy rain ahead — protect crop and drainage"
    elif heat:
        lvl, head = "caution", "Very hot — do field work early morning"
    elif spray:
        lvl, head = "good", f"Good to spray: {spray[0]['day']} {spray[0]['range']}"
    else:
        lvl, head = "ok", "Field conditions are workable, spraying is not ideal"
    detail = f"Rain 24h: {rain24} mm · 48h: {rain48} mm" + (f" · topsoil {soil_word}" if soil_word else "")
    nb = E.now_block(s)
    stats = [_stat("🌧️", "Rain (24h)", f"{rain24} mm"), _stat("🌱", "Topsoil", soil_word or "n/a", "model estimate"),
             _stat("💨", "Wind now", f"{nb['wind']} km/h", "spray drifts above 15"), _stat("💧", "Humidity", f"{nb['humidity']}%")]
    dos = ["Spray in calm, dry, cooler hours", "Drain excess water if heavy rain is due"] if rain24 >= 15 else ["Plan field work for the cooler part of the day", "Check soil before irrigating"]
    donts = ["Don't spray if rain is due within 6 hours", "Don't spray in strong wind — it drifts and wastes product"]
    why = _why([f"Rain next 48h: {rain48} mm", f"Evaporation next 48h: about {et48} mm", f"Wind now: {nb['wind']} km/h"],
               "Spraying works best with light wind and no rain for ~6 hours; irrigation depends on rain versus evaporation.",
               (spray[0]["why"][0].capitalize() + " → " + spray[0]["range"]) if spray else "Wait for a calmer, drier window.")
    return _verdict(lvl, head, detail), stats, cards, dos, donts, why, {}


def _sea_at(s, i):
    m = s.marine
    if not m:
        return None
    h = m["hourly"]
    try:
        j = h["time"].index(s.t[i])
    except ValueError:
        return None
    w = h["wave_height"][j]
    return {"wave": w, "period": (h.get("wave_period") or [None] * (j + 1))[j], "swell": (h.get("swell_wave_height") or [None] * (j + 1))[j]} if w is not None else None


def fisherman(s, profile):
    coastal = [c for c in cities.CITIES if c["coastal"]][:0] or [c for c in cities.CITIES if c["coastal"] and c["scan"]]
    quick = [{"name": c["name"], "lat": c["lat"], "lon": c["lon"]} for c in coastal][:8]
    a, b = s.i0, min(s.n, s.i0 + 24)
    if not s.marine or _sea_at(s, a) is None:
        v = _verdict("ok", "No sea data for this spot", f"{s.name} looks inland or too far from open water. Pick a coastal place to see wave conditions.")
        return v, [], [{"type": "note", "title": "Choose a coastal location", "tone": "ok", "text": "Wave height needs a point at sea or on the coast. Try one of the coastal cities below."}], \
            ["Follow official fishermen warnings from IMD / INCOIS"], [], _why([], "Marine forecasts only exist for coastal waters.", "Search a coastal city."), {"quick_places": quick}
    rows, levels = [], []
    for i in range(a, b, 3):
        sea = _sea_at(s, i)
        if not sea:
            continue
        wave, gust = sea["wave"], s.gust(i)
        thunder = is_thunder(s.code(i))
        st = "avoid" if (wave >= 2.5 or gust >= 45 or thunder) else "caution" if (wave >= 1.5 or gust >= 30 or s.precip(i) >= 2.5) else "good"
        levels.append(LEVEL[st])
        rows.append({"label": s.label(i), "day": s.day_name(i), "wave": round(wave, 1), "period": sea["period"], "wind": round(s.wind(i)), "gust": round(gust), "status": st,
                     "note": "thunderstorm risk" if thunder else ""})
    good_hours = [i for i in range(a, b) if (lambda sea: sea and sea["wave"] < 1.5 and s.gust(i) < 30 and not is_thunder(s.code(i)))(_sea_at(s, i))]
    cards = [{"type": "sea", "title": "Sea state — next 24 hours", "rows": rows}]
    if good_hours:
        sp = max(E._spans(good_hours), key=lambda x: x[1] - x[0])
        cards.append({"type": "note", "title": "Calmest stretch", "tone": "good",
                      "text": f"{s.label(sp[0])} – {s.label(sp[1] + 1)} has the calmest water (waves under 1.5 m, gusts under 30 km/h). Plan to be back before conditions change."})
    else:
        cards.append({"type": "note", "title": "Calmest stretch", "tone": "warn", "text": "No calm stretch in the next 24 hours."})
    cards.append({"type": "note", "title": "Important", "tone": "ok", "text": "This is model guidance, not an official warning. Always follow IMD / INCOIS fishermen warnings and your harbour authority; never go out during a cyclone or high-wave alert."})
    worst = max(levels) if levels else 0
    lvl = FROM_LEVEL[worst]
    sea0 = _sea_at(s, a)
    head = {"good": "Calm seas — good conditions", "ok": "Fair seas", "caution": "Choppy — be careful", "avoid": "Rough sea — stay ashore"}[lvl]
    peak_wave = max((r["wave"] for r in rows), default=0)
    detail = f"Waves {round(sea0['wave'], 1)} m now, up to {peak_wave} m in the next 24 hours."
    stats = [_stat("🌊", "Wave height", f"{round(sea0['wave'], 1)} m", f"period {sea0['period']} s" if sea0.get("period") else ""),
             _stat("💨", "Gusts", f"{round(s.gust(a))} km/h"), _stat("⛈️", "Thunder risk", "Yes" if any(is_thunder(s.code(i)) for i in range(a, b)) else "Low"),
             _stat("🌊", "Peak (24h)", f"{peak_wave} m")]
    why = _why([f"Waves now {round(sea0['wave'], 1)} m", f"Gusts up to {round(max(s.gust(i) for i in range(a, b)))} km/h"],
               "Small boats are at risk when waves pass ~2 m or gusts pass ~45 km/h; thunderstorms add lightning risk.", "Head out only during the calm stretch and return early.")
    return _verdict(lvl, head, detail), stats, cards, ["Carry life jackets and a charged phone/radio", "Tell someone your return time"], ["Don't go out if a cyclone or high-wave alert is active"], why, {"quick_places": quick}


def aviation(s, profile):
    a, b = s.i0, min(s.n, s.i0 + 14)
    rows, levels = [], []
    for i in range(a, b, 2):
        vis = s.vis(i) / 1000
        gk = s.gust(i) / 1.852
        th = is_thunder(s.code(i)) or (s.cape(i) >= 2000 and s.pop(i) >= 50)
        cat = "avoid" if (th or vis < 3 or gk > 35) else "caution" if (vis < 5 or gk > 25 or s.wet(i)) else "good"
        levels.append(LEVEL[cat])
        rows.append({"label": s.label(i), "vis": round(min(vis, 30), 1), "wind_kt": round(s.wind(i) / 1.852), "gust_kt": round(gk), "cloud": round(s.cloud(i)), "thunder": bool(th), "status": cat})
    lvl = FROM_LEVEL[max(levels) if levels else 0]
    nb = E.now_block(s)
    head = {"good": "Good flying weather (indicative)", "ok": "Acceptable", "caution": "Marginal conditions — check closely", "avoid": "Poor flying conditions"}[lvl]
    th_any = any(r["thunder"] for r in rows)
    detail = f"Visibility {round(min(s.vis(s.i0), 30000) / 1000, 1)} km, wind {round(s.wind(s.i0) / 1.852)} kt (gusts {round(s.gust(s.i0) / 1.852)} kt), cloud cover {nb['cloud']}%."
    cards = [{"type": "avi", "title": "Next 14 hours (every 2 h)", "rows": rows},
             {"type": "note", "title": "Not for flight planning", "tone": "ok", "text": "Model-based, indicative only. For real operations use official IMD aviation products (METAR/TAF/SIGMET) and airport briefings."}]
    stats = [_stat("👁️", "Visibility", f"{round(min(s.vis(s.i0), 30000) / 1000, 1)} km"), _stat("🧭", "Wind", f"{round(s.wind(s.i0) / 1.852)} kt", f"gusts {round(s.gust(s.i0) / 1.852)} kt"),
             _stat("☁️", "Cloud cover", f"{nb['cloud']}%"), _stat("⛈️", "Thunder", "Possible" if th_any else "Low risk")]
    if nb.get("pressure"):
        stats[2] = _stat("🎚️", "Sea-level pressure", f"{round(nb['pressure'])} hPa", f"cloud {nb['cloud']}%")
    why = _why([f"Visibility {round(min(s.vis(s.i0), 30000) / 1000, 1)} km", f"Gusts {round(s.gust(s.i0) / 1.852)} kt"], "Thunderstorms, low visibility and strong gusts are the main limits for light aircraft and drones.", "Re-check official METAR/TAF before flying.")
    return _verdict(lvl, head, detail), stats, cards, ["Check official METAR/TAF before every flight"], ["Don't fly near thunderstorms or in low-visibility fog"], why, {}


BUILDERS = {"office": office, "student": student, "commuter": commuter, "delivery": delivery, "fitness": fitness, "parent": parent,
            "traveler": traveler, "farmer": farmer, "fisherman": fisherman, "aviation": aviation}


def build(persona, s, profile=None):
    profile = profile or {}
    persona = persona if persona in PERSONAS else "office"
    meta = PERSONAS[persona]
    verdict, stats, cards, dos, donts, why, extra = BUILDERS[persona](s, profile)
    out = {
        "persona": persona, "title": meta["name"], "emoji": meta["emoji"], "tag": meta["tag"], "place": s.name,
        "lat": s.place.get("lat"), "lon": s.place.get("lon"), "updated": E.hm12(s.now_dt), "source": s.source,
        "verdict": verdict, "stats": stats, "cards": cards, "dos": dos, "donts": donts, "why": why,
        "strip": _strip(s, meta["act"]), "confidence": s.conf(s.i0 + 6),
        "disclaimer": "Guidance based on forecast models — you make the final call. Not a safety guarantee.",
    }
    out.update({k: v for k, v in extra.items() if k == "quick_places"})
    return out
