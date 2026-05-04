# tracker/forms.py
"""Form definitions for daily logs and user profile settings."""

from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import DailyLog, UserProfile
from .services import openweather


class DailyLogForm(forms.ModelForm):
    """Form used to create/update one DailyLog record.

    Applies UI widget classes and validates date uniqueness per user.
    """

    def __init__(self, *args, user=None, **kwargs):
        """Initialize widgets and remember current user for duplicate checks."""
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
            if field_name == "had_migraine" or field_name == "menstruation" or field_name == "show_menstruation":
                field.widget.attrs["class"] = f"{existing_classes} form-check-input ms-0".strip()
                if field_name == "had_migraine":
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
        # Alternatively, define an explicit `fields` list.

    def clean_date(self):
        """Block future dates at form-validation level."""
        d = self.cleaned_data.get("date")
        if d and d > timezone.localdate():
            raise ValidationError(_("You cannot log a future date."))
        return d

    def clean(self):
        """Run cross-field validation and migraine-conditional requirements."""
        cleaned = super().clean()
        d = cleaned.get("date")
        had = cleaned.get("had_migraine")

        # Prevent duplicates (but allow editing existing instance)
        if self.user and d:
            qs = DailyLog.objects.filter(user=self.user, date=d)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(_("You already have a log for this date. Edit the existing one instead."))

        # Migraine conditional requirements
        if had:
            if cleaned.get("migraine_intensity") is None:
                self.add_error("migraine_intensity", _("Required when 'Had migraine' is checked."))
            if cleaned.get("migraine_duration_hours") is None:
                self.add_error("migraine_duration_hours", _("Required when 'Had migraine' is checked."))
        else:
            cleaned["migraine_intensity"] = None
            cleaned["migraine_duration_hours"] = None
            cleaned["meds_taken"] = ""

        return cleaned


class ProfileForm(forms.ModelForm):
    """Profile settings form including city and language preferences."""

    class Meta:
        model = UserProfile
        fields = ["city", "show_menstruation", "preferred_language"]
        widgets = {
            "city": forms.TextInput(attrs={
                "class": "form-control log-input",
                "placeholder": _("Enter city name...")
            }),
            "show_menstruation": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
            "preferred_language": forms.HiddenInput()
        }

    def clean_city(self):
        """Validate city name through geocoding to catch unsupported inputs."""
        city = self.cleaned_data.get("city")
        if city:
            try:
                # Validate city via geocoding
                openweather.geocode(city)
            except Exception:
                raise ValidationError(
                    _("Could not validate city '{city}'. Please enter a valid city name that OpenWeather knows.").format(city=city)
                )
        return city