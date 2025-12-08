# tracker/views.py
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import DailyLogForm
from .models import UserProfile, DailyLog
from .services import openweather


@login_required(login_url="/admin/login/")
def home(request):
    qs = DailyLog.objects.filter(user=request.user).order_by("-date")[:14]
    logs = list(reversed(qs))

    has_data = len(logs) > 0

    labels = [log.date.strftime("%d.%m") for log in logs]

    def num_or_none(value):
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

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
        "temp_json": json.dumps(temp),
        "pressure_json": json.dumps(pressure),
        "humidity_json": json.dumps(humidity),
    }
    return render(request, "tracker/home.html", context)


@login_required(login_url="/admin/login/")
def log_day(request):
    # default date is "today"
    initial = {"date": timezone.localdate()}

    if request.method == "POST":
        form = DailyLogForm(request.POST)
        if form.is_valid():
            log: DailyLog = form.save(commit=False)
            log.user = request.user

            # Try to attach weather snapshot
            try:
                profile = UserProfile.objects.get(user=request.user)
                city = profile.city or "Bratislava"  # fallback if empty
            except UserProfile.DoesNotExist:
                city = "Bratislava"

            try:
                weather = openweather.get_current_weather(city)
            except Exception:
                weather = None

            if weather:
                log.weather_temp_c = weather["temp"]
                log.weather_humidity = weather["humidity"]
                log.weather_pressure_hpa = weather["pressure"]
                log.weather_wind_speed = weather["wind"]
                log.weather_cloudiness = weather["clouds"]
                log.weather_description = weather["description"]

            log.save()
            return redirect("tracker:home")
    else:
        form = DailyLogForm(initial=initial)

    context = {
        "form": form,
        "active_tab": "log",
    }
    return render(request, "tracker/log_form.html", context)
