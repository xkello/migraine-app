from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.conf import settings


class UserProfile(models.Model):
    """
    Extra info for each user, mainly where they live
    so we know which city's weather to use.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    city = models.CharField(max_length=100, blank=True)
    show_menstruation = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile({self.user.username})"



class DailyLog(models.Model):
    """
    One log entry (usually per day) with:
    - user lifestyle data
    - migraine info
    - weather snapshot at the time of logging
    """
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()

    sleep_hours = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(24)]
    )
    physical_activity_minutes = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    stress_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    caffeine_mg = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(3000)]
    )

    # New fields
    physical_activity_difficulty = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    heavy_meals = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    hydration_liters = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    alcohol_consumption = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    menstruation = models.BooleanField(default=False)

    had_migraine = models.BooleanField(default=False)
    migraine_intensity = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    migraine_duration_hours = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(72)]
    )
    meds_taken = models.CharField(max_length=255, blank=True)
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
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="uniq_log_per_user_per_date"),
        ]

    def clean(self):
        # If no migraine wipe migraine-only fields
        if not self.had_migraine:
            self.migraine_intensity = None
            self.migraine_duration_hours = None
            self.meds_taken = ""
        else:
            # If had migraine require intensity (and optionally duration)
            if self.migraine_intensity is None:
                raise ValidationError({"migraine_intensity": "Required when 'Had migraine' is checked."})
            if self.migraine_duration_hours is None:
                raise ValidationError({"migraine_duration_hours": "Required when 'Had migraine' is checked."})

    def __str__(self):
        return f"Log({self.user.username} @ {self.date})"