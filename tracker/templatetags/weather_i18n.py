from django import template
from django.utils.translation import gettext as _


register = template.Library()


@register.filter
def weather_i18n(value):
    """Translate OpenWeather description text using locale catalogs."""
    if not value:
        return ""
    normalized = str(value).strip().lower()
    return _(normalized)
