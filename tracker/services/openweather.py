import requests
from django.conf import settings

from collections import Counter,defaultdict
from datetime import datetime, time as dtime, timezone as dt_timezone
from django.utils import timezone



class WeatherAPIError(Exception):
    pass


def _to_celsius(x):
    # OpenWeather history often returns Kelvin
    if x is None:
        return None
    return x - 273.15 if x > 100 else x


# Low-level request helper
def _call(base_url, endpoint, params):
    params["appid"] = settings.WEATHER_API_KEY
    url = f"{base_url}{endpoint}"

    response = requests.get(url, params=params, timeout=10)

    if response.status_code != 200:
        raise WeatherAPIError(
            f"{response.status_code}: {response.text}"
        )
    return response.json()


# Geocoding (city → lat/lon)
def geocode(city: str):
    data = _call(
        settings.OWM_API_BASE,
        "/geo/1.0/direct",
        {"q": city, "limit": 1},
    )
    if not data:
        raise WeatherAPIError(f"City not found: {city}")

    return {
        "lat": data[0]["lat"],
        "lon": data[0]["lon"],
        "name": data[0]["name"],
        "country": data[0]["country"],
    }


def _get_loc(city_or_loc):
    if isinstance(city_or_loc, dict) and "lat" in city_or_loc and "lon" in city_or_loc:
        return city_or_loc
    return geocode(city_or_loc)


# CURRENT WEATHER
def get_current_weather(city_or_loc):
    loc = _get_loc(city_or_loc)
    data = _call(
        settings.OWM_API_BASE,
        "/data/2.5/weather",
        {"lat": loc["lat"], "lon": loc["lon"], "units": "metric"},
    )

    return {
        "location": loc,
        "temp": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind": data["wind"]["speed"],
        "description": data["weather"][0]["description"],
        "clouds": data["clouds"]["all"],
    }


# FORECAST (5-day, 3h intervals)
def get_forecast(city_or_loc, days: int = 3):
    loc = _get_loc(city_or_loc)
    data = _call(
        settings.OWM_API_BASE,
        "/data/2.5/forecast",
        {"lat": loc["lat"], "lon": loc["lon"], "units": "metric"},
    )

    parsed = []
    for e in data["list"]:
        parsed.append({
            "time": e["dt_txt"],
            "temp": e["main"]["temp"],
            "humidity": e["main"]["humidity"],
            "pressure": e["main"]["pressure"],
            "wind": e["wind"]["speed"],
            "clouds": e["clouds"]["all"],
            "description": e["weather"][0]["description"],
        })

    return {
        "location": data["city"]["name"],
        "forecast": parsed,
    }


def get_daily_forecast(city_or_loc, days: int = 3):
    """
    Uses 5-day/3h forecast and aggregates per-day averages.
    Returns list of dicts: {date, temp, pressure, humidity}
    """
    data = get_forecast(city_or_loc)
    buckets = defaultdict(list)

    for e in data["forecast"]:
        # e["time"] is like '2025-12-06 18:00:00'
        d = e["time"].split(" ")[0]  # YYYY-MM-DD
        buckets[d].append(e)

    daily = []
    for day_str in sorted(buckets.keys()):
        vals = buckets[day_str]

        def avg(key):
            xs = [v.get(key) for v in vals if v.get(key) is not None]
            return sum(xs) / len(xs) if xs else None

        daily.append({
            "date": day_str,  # YYYY-MM-DD
            "temp": avg("temp"),
            "pressure": avg("pressure"),
            "humidity": avg("humidity"),
        })

    # keep only next N days starting tomorrow
    return daily[:days+1]



# HISTORICAL WEATHER (PAID API)
def get_historical_weather(city_or_loc, start, end, interval="hour"):
    """
    start/end = UNIX timestamps
    interval = "hour" or "day"
    """

    loc = _get_loc(city_or_loc)

    data = _call(
        settings.OWM_HISTORY_BASE,
        "/data/2.5/history/city",
        {
            "lat": loc["lat"],
            "lon": loc["lon"],
            "type": interval,
            "start": start,
            "end": end,
            "units": "metric",
        },
    )

    results = []
    for e in data.get("list", []):
        results.append({
            "time": e["dt"],
            "temp": e["main"]["temp"],
            "humidity": e["main"]["humidity"],
            "pressure": e["main"]["pressure"],
            "wind": e["wind"]["speed"],
            "clouds": e["clouds"]["all"],
        })

    return results


# AIR QUALITY
def get_air_quality(city_or_loc):
    loc = _get_loc(city_or_loc)
    data = _call(
        settings.OWM_API_BASE,
        "/data/2.5/air_pollution",
        {"lat": loc["lat"], "lon": loc["lon"]},
    )

    comp = data["list"][0]["components"]
    return {
        "aqi": data["list"][0]["main"]["aqi"],
        "pm25": comp["pm2_5"],
        "pm10": comp["pm10"],
        "no2": comp["no2"],
        "o3": comp["o3"],
    }


def get_weather_for_date(city_or_loc, day):
    """
    One representative snapshot for a date.
    - past -> historical (avg over the day)
    - today -> current
    - future -> forecast (closest to 12:00 local time)
    """
    loc = _get_loc(city_or_loc)
    today = timezone.localdate()

    if day < today:
        # historical: full day in local time
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(day, dtime.min), tz)
        end_dt = timezone.make_aware(datetime.combine(day, dtime.max), tz)

        start_ts = int(start_dt.timestamp())
        end_ts = int(end_dt.timestamp())

        rows = get_historical_weather(loc, start_ts, end_ts, interval="hour")
        if not rows:
            raise WeatherAPIError(f"No historical data returned for {loc.get('name', city_or_loc)} on {day}")

        def avg(key):
            vals = [r.get(key) for r in rows if r.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        descs = [r.get("description") for r in rows if r.get("description")]
        most_common_desc = Counter(descs).most_common(1)[0][0] if descs else ""

        return {
            "location": loc,
            "temp": avg("temp"),
            "humidity": avg("humidity"),
            "pressure": avg("pressure"),
            "wind": avg("wind"),
            "clouds": avg("clouds"),
            "description": most_common_desc,
        }

    if day == today:
        return get_current_weather(loc)

    # future -> forecast
    data = _call(
        settings.OWM_API_BASE,
        "/data/2.5/forecast",
        {"lat": loc["lat"], "lon": loc["lon"], "units": "metric"},
    )

    tz = timezone.get_current_timezone()
    target = timezone.make_aware(datetime.combine(day, dtime(hour=12)), tz)

    best_item = None
    best_diff = None

    for item in data.get("list", []):
        # item["dt"] is UTC seconds
        dt_local = timezone.localtime(datetime.fromtimestamp(item["dt"], tz=dt_timezone.utc), tz)
        if dt_local.date() != day:
            continue
        diff = abs((dt_local - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_item = item

    if not best_item:
        raise WeatherAPIError(f"No forecast data returned for {loc.get('name', city_or_loc)} on {day}")

    return {
        "location": loc,
        "temp": best_item["main"]["temp"],
        "humidity": best_item["main"]["humidity"],
        "pressure": best_item["main"]["pressure"],
        "wind": best_item["wind"]["speed"],
        "clouds": best_item["clouds"]["all"],
        "description": (best_item.get("weather") or [{}])[0].get("description", ""),
    }