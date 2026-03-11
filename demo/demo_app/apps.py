"""App configuration for the demo application."""

from django.apps import AppConfig


class DemoAppConfig(AppConfig):
    """Configuration for the demo app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "demo_app"
    verbose_name = "Demo Application"

    def ready(self):
        from django_dolt.admin import register_dolt_status_view

        register_dolt_status_view()
