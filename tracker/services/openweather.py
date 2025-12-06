import requests
from django.conf import settings

class WeatherAPIError(Exception):
    pass


# -----------------------------
# Low-level request helper
# -----------------------------
def _call(base_url, endpoint, params):
    params["appid"] = settings.WEATHER_API_KEY
    url = f"{base_url}{endpoint}"

    response = requests.get(url, params=params, timeout=10)

    if response.status_code != 200:
        raise WeatherAPIError(
            f"{response.status_code}: {response.text}"
        )
    return response.json()


# -----------------------------
# Geocoding (city → lat/lon)
# -----------------------------
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


# -----------------------------
# CURRENT WEATHER
# -----------------------------
def get_current_weather(city: str):
    loc = geocode(city)
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


# -----------------------------
# FORECAST (5-day, 3h intervals)
# -----------------------------
def get_forecast(city: str):
    loc = geocode(city)
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


# -----------------------------
# HISTORICAL WEATHER (PAID API)
# -----------------------------
def get_historical_weather(city: str, start, end, interval="hour"):
    """
    start/end = UNIX timestamps
    interval = "hour" or "day"
    """

    loc = geocode(city)

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


# -----------------------------
# AIR QUALITY
# -----------------------------
def get_air_quality(city: str):
    loc = geocode(city)
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
