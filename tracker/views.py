from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse


@login_required(login_url="/admin/login/")  # later make a proper login
def home(request):
    # For now, send some dummy data for charts
    context = {
        "user_name": request.user.username or "friend",
        "sleep_hours": [7, 6, 8, 5, 7.5, 6.5, 8],  # fake last 7 days
        "migraine_intensity": [0, 3, 0, 5, 1, 0, 2],
        "pressure": [1015, 1012, 1018, 1009, 1011, 1013, 1016],
    }
    return render(request, "tracker/home.html", context)


@login_required(login_url="/admin/login/")
def log_day(request):
    # Placeholder – later this will show a real form
    context = {
        "active_tab": "log",
    }
    return render(request, "tracker/log_placeholder.html", context)
