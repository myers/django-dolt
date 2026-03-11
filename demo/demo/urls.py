"""URL configuration for django-dolt demo application."""

from django.urls import include, path

from .admin import dolt_admin_site

urlpatterns = [
    path("admin/", dolt_admin_site.urls),
    path("", include("demo_app.urls")),
]
