from django.db import models
from django.conf import settings



class DailyLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()

    # Inputs / triggers
    sleep_hours = models.FloatField(null=True, blank=True)
    physical_activity_minutes = models.IntegerField(null=True, blank=True)
    stress_level = models.IntegerField(null=True, blank=True)  # 1–5
    caffeine_mg = models.IntegerField(null=True, blank=True)
    screen_time_hours = models.FloatField(null=True, blank=True)

    # Migraine outcome
    migraine_occurred = models.BooleanField(default=False)
    migraine_intensity = models.IntegerField(null=True, blank=True)  # 1–10
    migraine_duration_hours = models.FloatField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.user} – {self.date}"