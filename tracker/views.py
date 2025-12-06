from django.contrib.auth.decorators import login_required
from django.shortcuts import render


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
    context = {
        "active_tab": "log",
    }
    return render(request, "tracker/log_placeholder.html", context)
