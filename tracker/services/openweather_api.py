# tracker/services/openweather_api.py
import datetime
import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class WeatherAPIError(Exception):
    """Custom exception for Weather API failures."""
    pass


def _get_base_params() -> Dict[str, Any]:
    try:
        api_key = settings.WEATHER_API_KEY
    except AttributeError:
        raise WeatherAPIError("WEATHER_API_KEY is not configured in settings_local.py")

    if not api_key:
        raise WeatherAPIError("WEATHER_API_KEY is empty")

    return {"key": api_key}


def _call_weatherapi(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    base_url = getattr(settings, "WEATHER_API_BASE_URL", "https://api.weatherapi.com/v1")
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    all_params = {**_get_base_params(), **params}

    try:
        response = requests.get(url, params=all_params, timeout=10)
    except requests.RequestException as e:
        logger.exception("WeatherAPI network error")
        raise WeatherAPIError(f"Network error calling WeatherAPI: {e}") from e

    if response.status_code != 200:
        logger.error("WeatherAPI returned non-200: %s %s", response.status_code, response.text)
        raise WeatherAPIError(f"WeatherAPI error {response.status_code}: {response.text}")

    return response.json()


def get_current_weather(location: str) -> Dict[str, Any]:
    """
    Fetch current weather for a location.

    `location` can be:
      - "Bratislava"
      - "48.15,17.11" (lat,lon)
      - ZIP code, etc., whatever WeatherAPI supports
    """
    data = _call_weatherapi(
        "current.json",
        {"q": location, "aqi": "yes"},
    )

    cur = data["current"]

    # Map to the fields we care about
    return {
        "location_name": data["location"]["name"],
        "country": data["location"]["country"],
        "lat": data["location"]["lat"],
        "lon": data["location"]["lon"],
        "time": data["location"]["localtime"],

        # core weather fields
        "temp_c": cur["temp_c"],
        "feelslike_c": cur.get("feelslike_c"),
        "humidity": cur["humidity"],
        "pressure_hpa": cur["pressure_mb"],
        "wind_kph": cur["wind_kph"],
        "wind_degree": cur["wind_degree"],
        "wind_dir": cur["wind_dir"],
        "cloud": cur["cloud"],
        "precip_mm": cur.get("precip_mm", 0.0),
        "uv": cur.get("uv"),
        "condition_text": cur["condition"]["text"],
        "condition_code": cur["condition"]["code"],

        # air quality (if enabled on your plan)
        "air_quality": cur.get("air_quality"),
    }


def get_daily_forecast(
    location: str,
    days: int = 3,
    date: Optional[datetime.date] = None,
) -> Dict[str, Any]:
    """
    Get a short forecast or history.

    - If `date` is None: forecast for the next `days` days.
    - If `date` is in the past: historical weather for that date (1 day window).

    We return daily averages + pressure, humidity etc.
    """
    if date is None or date >= datetime.date.today():
        # forecast
        data = _call_weatherapi(
            "forecast.json",
            {
                "q": location,
                "days": days,
                "aqi": "no",
                "alerts": "no",
            },
        )
        days_data = data["forecast"]["forecastday"]
    else:
        # history for one specific past date
        data = _call_weatherapi(
            "history.json",
            {
                "q": location,
                "dt": date.isoformat(),
            },
        )
        days_data = data["forecast"]["forecastday"]

    # Normalize into a list of daily dicts
    normalized = []
    for d in days_data:
        day = d["day"]
        normalized.append(
            {
                "date": d["date"],
                "avgtemp_c": day["avgtemp_c"],
                "maxtemp_c": day["maxtemp_c"],
                "mintemp_c": day["mintemp_c"],
                "avghumidity": day["avghumidity"],
                "daily_chance_of_rain": day.get("daily_chance_of_rain"),
                "totalprecip_mm": day["totalprecip_mm"],
                "maxwind_kph": day["maxwind_kph"],
                # pressure is usually only hourly, so later
                # call the hourly API and average it yourself.
                "condition_text": day["condition"]["text"],
                "condition_code": day["condition"]["code"],
            }
        )

    return {
        "location_name": data["location"]["name"],
        "country": data["location"]["country"],
        "lat": data["location"]["lat"],
        "lon": data["location"]["lon"],
        "days": normalized,
    }
