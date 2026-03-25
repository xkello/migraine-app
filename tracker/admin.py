from django.contrib import admin
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.admin.sites import NotRegistered
from .models import DailyLog, UserProfile

# Allow non-staff users to log in via admin login page
admin.site.login_form = AuthenticationForm
admin.site.has_permission = lambda r: r.user.is_active

User = get_user_model()


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = DjangoUserAdmin.list_display + (
        "missed_days_count",
        "missed_in_group",
    )

    @admin.display(description="Missed days")
    def missed_days_count(self, obj):
        profile = getattr(obj, "userprofile", None)
        return profile.missed_days_count if profile else 0

    @admin.display(boolean=True, description="In missed group")
    def missed_in_group(self, obj):
        return obj.groups.filter(name="missed_daily_log").exists()


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
