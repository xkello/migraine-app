# tracker/views.py
import json
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .forms import DailyLogForm
from .models import UserProfile, DailyLog
from .services import openweather
from datetime import timedelta, datetime



logger = logging.getLogger(__name__)
CITY = getattr(settings, "DEFAULT_CITY", "Bratislava")

@login_required(login_url="/admin/login/")
def home(request):
    qs = DailyLog.objects.filter(user=request.user).order_by("-date")[:120]
    logs = list(reversed(qs))
    has_data = len(logs) > 0

    def num_or_none(value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception as e:
            logger.warning("Cannot be 0", e)
            return None

    #labels = [log.date.strftime("%d.%m") for log in logs]
    labels = [log.date.isoformat() for log in logs]
    sleep = [num_or_none(log.sleep_hours) for log in logs]
    activity = [log.physical_activity_minutes or 0 for log in logs]
    stress = [log.stress_level or 0 for log in logs]
    caffeine = [log.caffeine_mg or 0 for log in logs]

    migraine_intensity = [
        log.migraine_intensity if log.had_migraine and log.migraine_intensity is not None else 0
        for log in logs
    ]
    migraine_duration = [
        num_or_none(log.migraine_duration_hours) if log.had_migraine else 0
        for log in logs
    ]
    had_migraine_flags = [1 if log.had_migraine else 0 for log in logs]

    # convert None -> null safely via json.dumps
    temp = [num_or_none(log.weather_temp_c) for log in logs]
    pressure = [log.weather_pressure_hpa for log in logs]
    humidity = [log.weather_humidity for log in logs]

    # City
    try:
        profile = UserProfile.objects.get(user=request.user)
        city = profile.city or "Bratislava"
    except UserProfile.DoesNotExist:
        city = "Bratislava"

    # WEATHER: build last 30 days (today-29..today) from logs + next 3 from forecast
    today = timezone.localdate()

    # Geocode once to save API calls
    try:
        loc = openweather.geocode(city)
    except Exception:
        loc = city

    # weather fixed window (30 past incl today + 3 future)
    past_days = [today - timedelta(days=i) for i in range(30, -1, -1)]  # 30 days ago .. today
    future_days = [today + timedelta(days=i) for i in range(1, 4)]  # tomorrow .. +3
    weather_labels = past_days + future_days

    # map logged weather by date (only logs that exist)
    by_date = {log.date: log for log in logs}

    w_temp = []
    w_pressure = []
    w_humidity = []

    for d in weather_labels:
        # 1) prefer saved weather from that day's log (if present)
        log = by_date.get(d)
        if log and log.weather_pressure_hpa is not None:
            w_temp.append(num_or_none(log.weather_temp_c))
            w_pressure.append(num_or_none(log.weather_pressure_hpa))
            w_humidity.append(num_or_none(log.weather_humidity))
            continue

        # 2) otherwise check cache
        cache_key = f"weather_{city}_{d.isoformat()}"
        w = cache.get(cache_key)
        if not w:
            # 3) fetch from API
            try:
                w = openweather.get_weather_for_date(loc, d)
                cache.set(cache_key, w, 60*60*24) # cache for 24 hours
            except Exception:
                w = None

        if w:
            w_temp.append(num_or_none(w.get("temp")))
            w_pressure.append(num_or_none(w.get("pressure")))
            w_humidity.append(num_or_none(w.get("humidity")))
        else:
            w_temp.append(None)
            w_pressure.append(None)
            w_humidity.append(None)

    context = {
        "user_name": request.user.username or "friend",
        "has_data": has_data,
        "active_tab": "home",

        # JSON versions for the template
        "labels_json": json.dumps(labels),
        "sleep_json": json.dumps(sleep),
        "activity_json": json.dumps(activity),
        "stress_json": json.dumps(stress),
        "caffeine_json": json.dumps(caffeine),

        "migraine_intensity_json": json.dumps(migraine_intensity),
        "migraine_duration_json": json.dumps(migraine_duration),
        "had_migraine_flags_json": json.dumps(had_migraine_flags),

        # weather fixed 10-day window (7 past incl today + 3 future)
        "weather_labels_json": json.dumps([d.isoformat() for d in weather_labels]),
        "weather_temp_json": json.dumps(w_temp),
        "weather_pressure_json": json.dumps(w_pressure),
        "weather_humidity_json": json.dumps(w_humidity),
    }
    return render(request, "tracker/home.html", context)


@login_required(login_url="/admin/login/")
def log_day(request):
    # def
    # ault date is "today"
    initial = {"date": timezone.localdate()}

    if request.method == "POST":
        form = DailyLogForm(request.POST)
        if form.is_valid():
            log: DailyLog = form.save(commit=False)
            log.user = request.user

            if log.date > timezone.localdate():
                form.add_error("date", "You cannot log a future date.")
                return render(request, "tracker/log_form.html", {"form": form, "active_tab": "log"})

            # Try to attach weather snapshot
            try:
                profile = UserProfile.objects.get(user=request.user)
                city = profile.city or "Bratislava"  # fallback if empty
            except UserProfile.DoesNotExist:
                city = "Bratislava"

            try:
                weather = openweather.get_weather_for_date(city, log.date)
            except Exception as e:
                logger.warning("Weather fetch failed for %s on %s: %s", city, log.date, e)
                weather = None

            if weather:
                log.weather_temp_c = weather["temp"]
                log.weather_humidity = weather["humidity"]
                log.weather_pressure_hpa = weather["pressure"]
                log.weather_wind_speed = weather["wind"]
                log.weather_cloudiness = weather["clouds"]
                log.weather_description = weather["description"] or ""

            log.save()
            return redirect("tracker:home")
    else:
        form = DailyLogForm(initial=initial)

    context = {
        "form": form,
        "active_tab": "log",
    }
    return render(request, "tracker/log_form.html", context)
