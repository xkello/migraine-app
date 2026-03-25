from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from .models import DailyLog, UserProfile

# Allow non-staff users to log in via admin login page
admin.site.login_form = AuthenticationForm
admin.site.has_permission = lambda r: r.user.is_active


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "had_migraine", "migraine_intensity", "sleep_hours")
    list_filter = ("had_migraine", "date")
    search_fields = ("user__username", "notes")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "city",
        "missed_days_count",
        "missed_days_last_incremented_on",
    )
    list_filter = ("missed_days_last_incremented_on",)
    search_fields = ("user__username", "city")
