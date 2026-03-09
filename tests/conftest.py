"""Pytest configuration for django-dolt tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Generator

import django
import pytest
from django.conf import settings

if TYPE_CHECKING:
    pass


def pytest_configure() -> None:
    """Configure Django settings for tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
    if not settings.configured:
        django.setup()


def is_dolt_available() -> bool:
    """Check if Dolt server is running and accessible."""
    if "dolt" not in settings.DATABASES:
        return False
    try:
        from django.db import connections

        conn = connections["dolt"]
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def dolt_databases(
    django_db_setup: None,
) -> Generator[list[str], None, None]:
    """Create two test databases in the Dolt server.

    Skips if Dolt server is not available.

    Args:
        django_db_setup: pytest-django fixture to ensure DB is set up.

    Yields:
        List of test database aliases.
    """
    if not is_dolt_available():
        pytest.skip("Dolt server not available")

    from django.db import connections

    conn = connections["dolt"]
    with conn.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS test_dolt1")
        cursor.execute("CREATE DATABASE IF NOT EXISTS test_dolt2")

    yield ["dolt1", "dolt2"]

    # Cleanup
    with conn.cursor() as cursor:
        cursor.execute("DROP DATABASE IF EXISTS test_dolt1")
        cursor.execute("DROP DATABASE IF EXISTS test_dolt2")
