from django.apps import AppConfig


class TrackerConfig(AppConfig):
    """Application configuration for the migraine tracker Django app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tracker'
