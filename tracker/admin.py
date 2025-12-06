from django.contrib import admin
from .models import DailyLog, UserProfile


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "had_migraine", "migraine_intensity", "sleep_hours")
    list_filter = ("had_migraine", "date")
    search_fields = ("user__username", "notes")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "city")
    search_fields = ("user__username", "city")
