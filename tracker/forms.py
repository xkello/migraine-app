# tracker/forms.py
from django import forms
from .models import DailyLog
from django.utils import timezone


class DailyLogForm(forms.ModelForm):
    class Meta:
        model = DailyLog
        fields = [
            "date",
            "sleep_hours",
            "physical_activity_minutes",
            "stress_level",
            "caffeine_mg",
            "had_migraine",
            "migraine_intensity",
            "migraine_duration_hours",
            "meds_taken",
            "notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].widget.attrs["max"] = timezone.localdate().isoformat()

        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({
                    "class": "form-check-input",
                })
            else:
                # all other inputs
                widget.attrs.update({
                    "class": "form-control form-control-sm log-input",
                })

    def clean_date(self):
        d = self.cleaned_data["date"]
        if d > timezone.localdate():
            raise forms.ValidationError("You cannot log a future date.")
        return d