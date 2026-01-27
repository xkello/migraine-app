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
from tracker.ml.predict import predict_next_day_risk



logger = logging.getLogger(__name__)
CITY = getattr(settings, "DEFAULT_CITY", "Bratislava")

@login_required(login_url="/admin/login/")
def home(request):
    qs = DailyLog.objects.filter(user=request.user).order_by("-date")[:120]
    logs = list(reversed(qs))
    has_data = len(logs) > 0

    def risk_label(p: float) -> str:
        # simple thresholds you can tweak later
        if p < 0.20:
            return "Low"
        if p < 0.50:
            return "Medium"
        return "High"

    def label_icon_css(label: str) -> str:
        if label == "Low":
            return "bi-check-circle-fill text-success"
        if label == "Medium":
            return "bi-exclamation-triangle-fill text-warning"
        return "bi-exclamation-octagon-fill text-danger"

    def friendly_feature_name(feat: str) -> str:
        # Map ML feature names to user-friendly text
        mapping = {
            "sleep_hours": "Sleep",
            "stress_level": "Stress",
            "caffeine_mg": "Caffeine",
            "hydration_liters": "Hydration",
            "alcohol_consumption": "Alcohol",
            "heavy_meals": "Heavy meals",
            "physical_activity_minutes": "Physical activity",
            "physical_activity_difficulty": "Activity difficulty",
            "menstruation": "Menstruation",
            "had_migraine_lag1": "Migraine yesterday",
            "weather_pressure_hpa": "Pressure",
            "weather_pressure_hpa_delta1": "Pressure change",
            "weather_temp_c": "Temperature",
            "weather_temp_c_delta1": "Temperature change",
            "weather_humidity": "Humidity",
            "weather_humidity_delta1": "Humidity change",
        }
        # Handle one-hot features like month_12 or weekday_3
        if feat.startswith("month_"):
            return f"Month ({feat.split('_', 1)[1]})"
        if feat.startswith("weekday_"):
            return f"Weekday ({feat.split('_', 1)[1]})"
        # Handle lag/rolling generic patterns
        if "_lag1" in feat:
            base = feat.replace("_lag1", "")
            return mapping.get(base, base) + " (yesterday)"
        if "_roll_mean_" in feat:
            base = feat.split("_roll_mean_", 1)[0]
            w = feat.split("_roll_mean_", 1)[1]
            return mapping.get(base, base) + f" (avg last {w} days)"
        if "migraine_roll_sum_" in feat:
            w = feat.split("migraine_roll_sum_", 1)[1]
            return f"Migraine count (last {w} days)"
        return mapping.get(feat, feat)


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
    activity_difficulty = [log.physical_activity_difficulty or 0 for log in logs]
    heavy_meals = [log.heavy_meals or 0 for log in logs]
    hydration = [num_or_none(log.hydration_liters) or 0 for log in logs]
    alcohol = [log.alcohol_consumption or 0 for log in logs]

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

    # ---- ML risk prediction (tomorrow risk using latest log) ----
    risk = {
        "available": False,
        "percent": None,
        "label": None,
        "icon_css": None,
        "summary": None,
        "reasons_up": [],
        "reasons_down": [],
    }

    if has_data:
        try:
            pred = predict_next_day_risk(user_id=request.user.id, with_explain=True)
            if pred.get("ok"):
                p = float(pred["p_final"])
                risk["available"] = True
                risk["percent"] = round(p * 100, 1)
                n_days = len(logs)
                if n_days < 30:
                    risk["confidence"] = "Low confidence (limited history)"
                elif n_days < 90:
                    risk["confidence"] = "Medium confidence"
                else:
                    risk["confidence"] = "High confidence"
                risk["label"] = risk_label(p)
                risk["icon_css"] = label_icon_css(risk["label"])

                # Build a short explanation from top contributors
                expl = pred.get("explain") or {}
                up = expl.get("top_positive", [])[:3]
                down = expl.get("top_negative", [])[:2]

                risk["reasons_up"] = [friendly_feature_name(x["feature"]) for x in up]
                risk["reasons_down"] = [friendly_feature_name(x["feature"]) for x in down]

                # Human-readable sentence
                def compact_join(items):
                    return ", ".join(items[:3])

                if risk["reasons_up"] or risk["reasons_down"]:
                    up_txt = compact_join(risk["reasons_up"])
                    down_txt = compact_join(risk["reasons_down"])

                    sentences = []
                    if up_txt:
                        sentences.append(f"Main factors increasing risk: {up_txt}.")
                    if down_txt:
                        sentences.append(f"Main factors decreasing risk: {down_txt}.")
                    risk["summary"] = " ".join(sentences)
                else:
                    risk["summary"] = "Not enough signals yet."
            else:
                risk["summary"] = pred.get("reason", "Prediction unavailable.")
        except Exception as e:
            logger.warning("Risk prediction failed: %s", e)
            risk["summary"] = "Prediction unavailable."
    else:
        risk["summary"] = "Add a few logs to get predictions."

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
        "activity_difficulty_json": json.dumps(activity_difficulty),
        "heavy_meals_json": json.dumps(heavy_meals),
        "hydration_json": json.dumps(hydration),
        "alcohol_json": json.dumps(alcohol),

        "migraine_intensity_json": json.dumps(migraine_intensity),
        "migraine_duration_json": json.dumps(migraine_duration),
        "had_migraine_flags_json": json.dumps(had_migraine_flags),

        # weather fixed 10-day window (7 past incl today + 3 future)
        "weather_labels_json": json.dumps([d.isoformat() for d in weather_labels]),
        "weather_temp_json": json.dumps(w_temp),
        "weather_pressure_json": json.dumps(w_pressure),
        "weather_humidity_json": json.dumps(w_humidity),

        "risk": risk,
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
