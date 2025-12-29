# tracker/views.py
import json
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache

from .forms import DailyLogForm, ProfileForm
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

    # Optimize weather fetching: check cache first for all labels
    weather_data_map = {}
    missing_dates = []

    for d in weather_labels:
        log = by_date.get(d)
        if log and log.weather_pressure_hpa is not None:
            weather_data_map[d] = {
                "temp": log.weather_temp_c,
                "pressure": log.weather_pressure_hpa,
                "humidity": log.weather_humidity
            }
            continue

        cache_key = f"weather_{city}_{d.isoformat()}"
        cached = cache.get(cache_key)
        if cached:
            weather_data_map[d] = cached
        else:
            missing_dates.append(d)

    # Bulk fetch missing dates
    if missing_dates:
        new_weather = openweather.get_weather_for_range(loc, missing_dates)
        for d, w in new_weather.items():
            # Convert string key back to date if necessary (get_weather_for_range returns date objects)
            # Actually get_weather_for_range returns {date_obj: weather_dict}
            if w:
                cache_key = f"weather_{city}_{d.isoformat()}"
                cache.set(cache_key, w, 60*60*24)
                weather_data_map[d] = w

    for d in weather_labels:
        w = weather_data_map.get(d)
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
        "logs": reversed(logs), # For the history list

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
    initial = {"date": timezone.localdate()}

    if request.method == "POST":
        # 1) get posted date (string) and parse to date
        posted_date_str = request.POST.get("date")
        posted_date = None
        if posted_date_str:
            try:
                posted_date = datetime.strptime(posted_date_str, "%Y-%m-%d").date()
            except ValueError:
                posted_date = None

        # 2) if a log already exists for that user+date, edit it instead of creating a new one
        existing = None
        if posted_date:
            existing = DailyLog.objects.filter(user=request.user, date=posted_date).first()

        # IMPORTANT: pass instance=existing
        form = DailyLogForm(request.POST, instance=existing, user=request.user)

        if form.is_valid():
            log: DailyLog = form.save(commit=False)
            log.user = request.user

            # safety (form also validates, but keep this)
            if log.date > timezone.localdate():
                form.add_error("date", "You cannot log a future date.")
                return render(request, "tracker/log_form.html", {"form": form, "active_tab": "log"})

            # city
            try:
                profile = UserProfile.objects.get(user=request.user)
                city = profile.city or "Bratislava"
            except UserProfile.DoesNotExist:
                city = "Bratislava"

            # attach weather snapshot for that date
            try:
                weather = openweather.get_weather_for_date(city, log.date)
            except Exception as e:
                logger.warning("Weather fetch failed for %s on %s: %s", city, log.date, e)
                weather = None
                from django.contrib import messages
                messages.warning(request, "Weather data was unavailable for this date.")

            if weather:
                log.weather_temp_c = weather.get("temp")
                log.weather_humidity = weather.get("humidity")
                log.weather_pressure_hpa = weather.get("pressure")
                log.weather_wind_speed = weather.get("wind")
                log.weather_cloudiness = weather.get("clouds")
                log.weather_description = weather.get("description") or ""

            log.save()
            from django.contrib import messages
            messages.success(request, "Log updated successfully!")
            return redirect("tracker:home")
    else:
        form = DailyLogForm(initial=initial)

    return render(request, "tracker/log_form.html", {"form": form, "active_tab": "log"})


@login_required(login_url="/admin/login/")
def edit_log(request, pk):
    log = get_object_or_404(DailyLog, pk=pk, user=request.user)
    if request.method == "POST":
        form = DailyLogForm(request.POST, instance=log, user=request.user)
        if form.is_valid():
            log = form.save(commit=False)
            # Re-fetch weather if date changed? For now keep existing or re-fetch.
            # Re-fetch is safer if date was edited.
            try:
                profile = UserProfile.objects.get(user=request.user)
                city = profile.city or "Bratislava"
            except UserProfile.DoesNotExist:
                city = "Bratislava"
            
            try:
                weather = openweather.get_weather_for_date(city, log.date)
                if weather:
                    log.weather_temp_c = weather.get("temp")
                    log.weather_humidity = weather.get("humidity")
                    log.weather_pressure_hpa = weather.get("pressure")
                    log.weather_wind_speed = weather.get("wind")
                    log.weather_cloudiness = weather.get("clouds")
                    log.weather_description = weather.get("description") or ""
            except Exception:
                pass

            log.save()
            from django.contrib import messages
            messages.success(request, "Changes saved!")
            return redirect("tracker:profile")
    else:
        form = DailyLogForm(instance=log)

    return render(request, "tracker/log_form.html", {
        "form": form,
        "active_tab": "log",
        "is_edit": True,
        "log_pk": log.pk
    })


@login_required(login_url="/admin/login/")
def delete_log(request, pk):
    log = get_object_or_404(DailyLog, pk=pk, user=request.user)
    if request.method == "POST":
        log.delete()
        return redirect("tracker:profile")
    return render(request, "tracker/log_confirm_delete.html", {"log": log})


@login_required(login_url="/admin/login/")
def profile(request):
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    if not user_profile.city:
        user_profile.city = "Bratislava"
        user_profile.save()

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, "Profile updated!")
            return redirect("tracker:profile")
    else:
        form = ProfileForm(instance=user_profile)

    logs = DailyLog.objects.filter(user=request.user).order_by("-date")

    context = {
        "user_profile": user_profile,
        "form": form,
        "logs": logs,
        "active_tab": "profile",
    }
    return render(request, "tracker/profile.html", context)
