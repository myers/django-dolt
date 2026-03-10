"""Pytest configuration for django-dolt tests."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Generator

import django
import pytest
from django.conf import settings


def _is_container_running() -> bool:
    """Check if the Dolt container is already running on port 8906."""
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--status=running", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        return "dolt" in result.stdout
    except Exception:
        return False


def _wait_for_healthy(timeout: int = 60) -> bool:
    """Wait for the Dolt container to be healthy."""
    import pymysql

    start = time.time()
    while time.time() - start < timeout:
        try:
            conn = pymysql.connect(
                host="127.0.0.1",
                port=8906,
                user="root",
                password="dolt",
            )
            conn.close()
            return True
        except Exception:
            time.sleep(1)
    return False


# Track whether we started docker compose
_we_started_docker = False


def pytest_configure() -> None:
    """Configure Django settings and ensure Dolt container is running."""
    global _we_started_docker

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

    # Always set Dolt connection env vars
    os.environ.setdefault("DOLT_HOST", "127.0.0.1")
    os.environ.setdefault("DOLT_PORT", "8906")
    os.environ.setdefault("DOLT_USER", "root")
    os.environ.setdefault("DOLT_PASSWORD", "dolt")

    if not settings.configured:
        django.setup()

    # Ensure Dolt container is running
    if not _is_container_running():
        project_root = os.path.dirname(os.path.dirname(__file__))
        subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=project_root,
            check=True,
        )
        _we_started_docker = True

    if not _wait_for_healthy():
        pytest.exit("Dolt container failed to become healthy", returncode=1)


def pytest_unconfigure() -> None:
    """Shut down Dolt container if we started it."""
    if _we_started_docker:
        project_root = os.path.dirname(os.path.dirname(__file__))
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=project_root,
        )


@pytest.fixture(scope="session")
def django_db_setup(
    request: pytest.FixtureRequest,
    django_test_environment: None,
    django_db_blocker: object,
) -> None:
    """Override pytest-django's db setup.

    Only creates the SQLite default database. Dolt databases are managed
    by test fixtures directly — they don't need Django's test DB creation.
    """
    from django.test.utils import setup_databases, teardown_databases

    with django_db_blocker.unblock():  # type: ignore[union-attr]
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            aliases=["default"],
        )

    yield

    with django_db_blocker.unblock():  # type: ignore[union-attr]
        teardown_databases(db_cfg, verbosity=request.config.option.verbose)


@pytest.fixture()
def dolt_databases() -> Generator[list[str], None, None]:
    """Create two test databases in the Dolt server.

    Yields:
        List of test database aliases.
    """
    from django.db import connections

    conn = connections["dolt"]
    with conn.cursor() as cursor:
        cursor.execute("DROP DATABASE IF EXISTS test_dolt1")
        cursor.execute("DROP DATABASE IF EXISTS test_dolt2")
        cursor.execute("CREATE DATABASE test_dolt1")
        cursor.execute("CREATE DATABASE test_dolt2")

    for alias in ("dolt1", "dolt2"):
        connections[alias].close()

    yield ["dolt1", "dolt2"]

    for alias in ("dolt1", "dolt2"):
        connections[alias].close()
    with conn.cursor() as cursor:
        cursor.execute("DROP DATABASE IF EXISTS test_dolt1")
        cursor.execute("DROP DATABASE IF EXISTS test_dolt2")
