from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    """
    Extra info for each user, mainly where they live
    so we know which city's weather to use.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    city = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Profile({self.user.username})"



class DailyLog(models.Model):
    """
    One log entry (usually per day) with:
    - user lifestyle data
    - migraine info
    - weather snapshot at the time of logging
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField(help_text="Day this log refers to")

    # Lifestyle / triggers
    sleep_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Hours of sleep for this night/day",
    )
    physical_activity_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Rough total minutes of physical activity (walking, exercise, etc.)",
    )
    stress_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Subjective stress 1–5",
    )
    caffeine_mg = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Approximate caffeine intake in mg (coffee, energy drinks…)",
    )

    # Migraine info
    had_migraine = models.BooleanField(default=False)
    migraine_intensity = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="0–10 if you had a migraine",
    )
    migraine_duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="How many hours the migraine lasted (approx.)",
    )
    meds_taken = models.CharField(
        max_length=200,
        blank=True,
        help_text="Medication taken, if any",
    )
    notes = models.TextField(blank=True)

    #created_at = models.DateTimeField(auto_now_add=True)

    # Weather snapshot at the time of logging (copied from OpenWeather)
    weather_temp_c = models.FloatField(null=True, blank=True)
    weather_humidity = models.IntegerField(null=True, blank=True)
    weather_pressure_hpa = models.IntegerField(null=True, blank=True)
    weather_wind_speed = models.FloatField(null=True, blank=True)
    weather_cloudiness = models.IntegerField(null=True, blank=True)
    weather_description = models.CharField(max_length=100, blank=True)

    #class Meta:
    #    unique_together = ("user", "date")
    #    ordering = ["-date"]

    class Meta:
        ordering = ["-date", "-created_at"]

    #def __str__(self):
    #    return f"{self.user} – {self.date}"

    def __str__(self):
        return f"Log({self.user.username} @ {self.date})"