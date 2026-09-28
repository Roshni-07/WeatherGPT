"""Convenience loader: forecast + air quality (+ marine) -> engine.Snap."""
import asyncio

from . import cities, engine as E, openmeteo as om


def resolve_name(lat, lon, given=None):
    if given:
        return given
    c, d = cities.nearest(lat, lon, 25)
    return c["name"] if c else "Your location"


async def load(lat, lon, name=None, marine=False, past_days=1, forecast_days=7):
    tasks = [om.forecast(lat, lon, past_days, forecast_days), om.air_quality(lat, lon)]
    if marine:
        tasks.append(om.marine(lat, lon))
    res = await asyncio.gather(*tasks)
    raw, aq = res[0], res[1]
    mar = res[2] if marine else None
    place = {"name": resolve_name(lat, lon, name), "lat": lat, "lon": lon}
    return E.Snap(raw, aq, mar, place, source="demo" if om.is_mock() else "live")
