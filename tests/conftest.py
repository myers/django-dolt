"""Pytest configuration for django-dolt tests."""

import os

import django
from django.conf import settings


def pytest_configure() -> None:
    """Configure Django settings for tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    if not settings.configured:
        django.setup()
