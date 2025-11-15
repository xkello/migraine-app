from django.contrib import admin
from .models import DailyLog


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "migraine_occurred", "migraine_intensity")
    list_filter = ("migraine_occurred", "date")
    search_fields = ("user__username", "notes")