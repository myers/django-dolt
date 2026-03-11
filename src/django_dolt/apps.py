"""Django app configuration for django-dolt."""

from django.apps import AppConfig


class DjangoDoltConfig(AppConfig):
    """Configuration for the django-dolt app."""

    name = "django_dolt"
    verbose_name = "Dolt Version Control"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        """Register admin classes for each discovered Dolt database.

        Set ``DOLT_AUTO_REGISTER_ADMIN = False`` in settings to disable
        auto-registration on ``admin.site`` (e.g. when using a custom
        admin site like ``DoltAdminSite`` that registers models itself).
        """
        from django.conf import settings

        if not getattr(settings, "DOLT_AUTO_REGISTER_ADMIN", True):
            return

        from django_dolt.admin import register_dolt_admin
        from django_dolt.dolt_databases import get_dolt_databases

        exclude = set(getattr(settings, "DOLT_ADMIN_EXCLUDE", []))
        dolt_databases = get_dolt_databases()
        for db_alias in dolt_databases:
            if db_alias not in exclude:
                register_dolt_admin(db_alias)
