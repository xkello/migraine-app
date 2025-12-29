# tracker/forms.py
from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import DailyLog, UserProfile
from .services import openweather


class DailyLogForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Use native date picker
        self.fields["date"].widget = forms.DateInput(attrs={
            "type": "date",
            "class": "form-control log-input",
            "max": timezone.localdate().isoformat()
        })

        # Add classes to all fields
        for field_name, field in self.fields.items():
            if field_name == "date":
                continue # Already handled
            existing_classes = field.widget.attrs.get("class", "")
            if field_name == "had_migraine":
                field.widget.attrs["class"] = f"{existing_classes} form-check-input".strip()
                field.widget.attrs["data-toggle-migraine"] = "true"
            elif field_name == "notes":
                field.widget.attrs["class"] = f"{existing_classes} form-control log-input".strip()
                field.widget.attrs["rows"] = 3
            else:
                field.widget.attrs["class"] = f"{existing_classes} form-control log-input".strip()

        # Block future dates in the UI
        self.fields["date"].widget.attrs["max"] = timezone.localdate().isoformat()
        self.fields["sleep_hours"].required = True
        self.fields["physical_activity_minutes"].required = True
        self.fields["stress_level"].required = True

    class Meta:
        model = DailyLog
        exclude = ("user", "weather_temp_c", "weather_humidity", "weather_pressure_hpa",
                   "weather_wind_speed", "weather_cloudiness", "weather_description")
        # or list your included fields explicitly if you prefer

    def clean_date(self):
        d = self.cleaned_data.get("date")
        if d and d > timezone.localdate():
            raise ValidationError("You cannot log a future date.")
        return d

    def clean(self):
        cleaned = super().clean()
        d = cleaned.get("date")
        had = cleaned.get("had_migraine")

        # Prevent duplicates (but allow editing existing instance)
        if self.user and d:
            qs = DailyLog.objects.filter(user=self.user, date=d)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("You already have a log for this date. Edit the existing one instead.")

        # Migraine conditional requirements
        if had:
            if cleaned.get("migraine_intensity") is None:
                self.add_error("migraine_intensity", "Required when 'Had migraine' is checked.")
            if cleaned.get("migraine_duration_hours") is None:
                self.add_error("migraine_duration_hours", "Required when 'Had migraine' is checked.")
        else:
            cleaned["migraine_intensity"] = None
            cleaned["migraine_duration_hours"] = None
            cleaned["meds_taken"] = ""

        return cleaned


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["city"]
        widgets = {
            "city": forms.TextInput(attrs={
                "class": "form-control log-input",
                "placeholder": "Enter city name..."
            })
        }

    def clean_city(self):
        city = self.cleaned_data.get("city")
        if city:
            try:
                # Validate city via geocoding
                openweather.geocode(city)
            except Exception:
                raise ValidationError(f"Could not validate city '{city}'. Please enter a valid city name that OpenWeather knows.")
        return city