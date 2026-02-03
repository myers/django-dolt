"""Django app configuration for django-dolt."""

from django.apps import AppConfig


class DjangoDoltConfig(AppConfig):
    """Configuration for the django-dolt app."""

    name = "django_dolt"
    verbose_name = "Dolt Version Control"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register admin classes for each discovered Dolt database."""
        from django_dolt.admin import enable_dolt_admin_grouping, register_dolt_admin
        from django_dolt.dolt_databases import get_dolt_databases

        dolt_databases = get_dolt_databases()
        for db_alias in dolt_databases:
            register_dolt_admin(db_alias)

        # Enable grouping by database in admin sidebar
        if dolt_databases:
            enable_dolt_admin_grouping()
