"""Django app configuration for django-dolt."""

from django.apps import AppConfig


class DjangoDoltConfig(AppConfig):
    """Configuration for the django-dolt app."""

    name = "django_dolt"
    verbose_name = "Dolt Version Control"
    default_auto_field = "django.db.models.BigAutoField"
