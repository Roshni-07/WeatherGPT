"""
Synthetic weather in the exact shape Open-Meteo returns. Used ONLY when
WEATHERGPT_MOCK=1 (offline demos, tests). Every response built from it is
tagged source="demo" so the UI shows a visible DEMO DATA badge.
"""
import math
import random
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def now_local():
    return datetime.now(IST).replace(tzinfo=None)


def _rng(lat, lon, tag=""):
    n = now_local()
    return random.Random(f"{round(lat, 1)}:{round(lon, 1)}:{n.date()}:{tag}")


def forecast(lat, lon, past_days=1, forecast_days=7, lite=False):
    now = now_local().replace(minute=0, second=0, microsecond=0)
    start = (now - timedelta(days=past_days)).replace(hour=0)
    total = (past_days + forecast_days) * 24
    rng = _rng(lat, lon)
    base = 31 - max(0, lat - 10) * 0.32 - (4 if lat > 30 else 0)
    events = []
    for _ in range(3):
        events.append({"at": rng.randint(past_days * 24, total - 10), "len": rng.randint(2, 5), "mm": rng.choice([0.6, 1.5, 4, 9, 14])})
    # a guaranteed rain event this evening for the demo, in ~1/2 of places
    if rng.random() < 0.55:
        tonight = int((now - start).total_seconds() // 3600) + rng.randint(3, 8)
        events.append({"at": tonight, "len": 3, "mm": rng.choice([3, 6, 11])})

    H = {k: [] for k in ["time", "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                          "precipitation_probability", "precipitation", "weather_code", "cloud_cover",
                          "visibility", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
                          "uv_index", "is_day", "cape", "et0_fao_evapotranspiration", "soil_moisture_0_to_1cm"]}
    for i in range(total):
        dt = start + timedelta(hours=i)
        hod = dt.hour
        temp = base + 5.5 * math.sin((hod - 9) / 24 * 2 * math.pi) + rng.uniform(-0.6, 0.6)
        mm, near = 0.0, 0
        for e in events:
            if e["at"] <= i < e["at"] + e["len"]:
                mm = max(mm, e["mm"] * rng.uniform(0.6, 1.2))
            near = max(near, 1 if e["at"] - 3 <= i < e["at"] + e["len"] else 0)
        cloud = min(100, (65 if mm else 25 + (25 if near else 0)) + rng.randint(-10, 15))
        hum = max(35, min(98, 88 - (temp - 24) * 2.6 + (10 if mm else 0)))
        pop = 85 if mm > 0.3 else (45 if near else rng.choice([2, 5, 8, 12]))
        day = 1 if 6 <= hod < 18 else 0
        gust = 10 + rng.uniform(0, 12) + (22 if mm > 8 else 0) + (6 if 13 <= hod <= 18 else 0)
        code = 0 if cloud < 20 else 1 if cloud < 40 else 2 if cloud < 70 else 3
        if mm >= 0.1:
            code = 61 if mm < 2.5 else 63 if mm < 7.6 else 65
        if mm >= 9:
            code = 95
        feels = temp + max(0, (hum - 50)) * 0.11
        H["time"].append(dt.strftime("%Y-%m-%dT%H:%M"))
        H["temperature_2m"].append(round(temp, 1))
        H["relative_humidity_2m"].append(round(hum))
        H["apparent_temperature"].append(round(feels, 1))
        H["precipitation_probability"].append(pop)
        H["precipitation"].append(round(mm, 1))
        H["weather_code"].append(code)
        H["cloud_cover"].append(int(cloud))
        H["visibility"].append(24000 if not mm else 6000)
        H["wind_speed_10m"].append(round(gust * 0.55, 1))
        H["wind_direction_10m"].append(int((200 + hod * 3) % 360))
        H["wind_gusts_10m"].append(round(gust, 1))
        H["uv_index"].append(round(max(0, 9.5 * math.sin((hod - 6) / 12 * math.pi)) * (0.4 if cloud > 60 else 1), 1) if day else 0)
        H["is_day"].append(day)
        H["cape"].append(1800 if mm >= 9 else 300)
        H["et0_fao_evapotranspiration"].append(round(max(0, 0.45 * math.sin((hod - 6) / 12 * math.pi)) if day else 0, 2))
        H["soil_moisture_0_to_1cm"].append(0.29 if mm else 0.22)

    ci = int((now - start).total_seconds() // 3600)
    cur = {
        "time": H["time"][ci], "temperature_2m": H["temperature_2m"][ci], "relative_humidity_2m": H["relative_humidity_2m"][ci],
        "apparent_temperature": H["apparent_temperature"][ci], "is_day": H["is_day"][ci], "precipitation": H["precipitation"][ci],
        "weather_code": H["weather_code"][ci], "cloud_cover": H["cloud_cover"][ci], "pressure_msl": 1006,
        "wind_speed_10m": H["wind_speed_10m"][ci], "wind_direction_10m": H["wind_direction_10m"][ci],
        "wind_gusts_10m": H["wind_gusts_10m"][ci],
    }
    days = sorted({t[:10] for t in H["time"]})
    D = {"time": days, "weather_code": [], "temperature_2m_max": [], "temperature_2m_min": [], "sunrise": [], "sunset": [],
         "uv_index_max": [], "precipitation_sum": [], "precipitation_probability_max": [], "wind_gusts_10m_max": []}
    for d in days:
        idx = [i for i, t in enumerate(H["time"]) if t[:10] == d]
        D["time"] = days
        D["temperature_2m_max"].append(max(H["temperature_2m"][i] for i in idx))
        D["temperature_2m_min"].append(min(H["temperature_2m"][i] for i in idx))
        D["precipitation_sum"].append(round(sum(H["precipitation"][i] for i in idx), 1))
        D["precipitation_probability_max"].append(max(H["precipitation_probability"][i] for i in idx))
        D["wind_gusts_10m_max"].append(max(H["wind_gusts_10m"][i] for i in idx))
        D["uv_index_max"].append(max(H["uv_index"][i] for i in idx))
        D["weather_code"].append(max(H["weather_code"][i] for i in idx))
        D["sunrise"].append(f"{d}T06:02")
        D["sunset"].append(f"{d}T18:14")
    return {"latitude": lat, "longitude": lon, "utc_offset_seconds": 19800, "timezone": "Asia/Kolkata",
            "current": cur, "hourly": H, "daily": D}


def air(lat, lon):
    r = _rng(lat, lon, "aq")
    base = 40 + max(0, lat - 20) * 9 + r.randint(0, 45)
    return {"current": {"us_aqi": int(base), "pm2_5": round(base * 0.45, 1), "pm10": round(base * 0.8, 1)}}


def marine(lat, lon):
    if not (lon < 76.5 or lon > 79.9) or lat > 24:
        raise RuntimeError("no marine data (inland)")
    r = _rng(lat, lon, "sea")
    now = now_local().replace(minute=0, second=0, microsecond=0)
    times, wave, per, swell = [], [], [], []
    for i in range(-24, 24 * 5):
        dt = now + timedelta(hours=i)
        times.append(dt.strftime("%Y-%m-%dT%H:%M"))
        w = 1.1 + 0.6 * math.sin(i / 9) + r.uniform(-0.1, 0.1) + (1.2 if 8 <= i <= 16 else 0)
        wave.append(round(max(0.3, w), 2)); per.append(round(7 + 2 * math.sin(i / 11), 1)); swell.append(round(max(0.2, w * 0.7), 2))
    return {"hourly": {"time": times, "wave_height": wave, "wave_period": per, "swell_wave_height": swell}}


def climate_tmax(lat, lon, tmax_today):
    r = _rng(lat, lon, "clim")
    mean = tmax_today - r.choice([-3.6, -0.5, 0.4, 3.2, 4.4])
    return {"mean": round(mean, 1), "std": 1.6, "years": 10}
