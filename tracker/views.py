# tracker/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from .forms import DailyLogForm
from .models import UserProfile, DailyLog
from .services import openweather


@login_required(login_url="/admin/login/")
def home(request):
    context = {
        "user_name": request.user.username or "friend",
        "sleep_hours": [7, 6, 8, 5, 7.5, 6.5, 8],
        "migraine_intensity": [0, 3, 0, 5, 1, 0, 2],
        "pressure": [1015, 1012, 1018, 1009, 1011, 1013, 1016],
        "active_tab": "home",
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
