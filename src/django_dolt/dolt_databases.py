"""Dolt database discovery.

Provides utilities for detecting which configured Django databases are Dolt databases.
"""

from __future__ import annotations

from django.db import connections

_dolt_databases: list[str] | None = None


def get_dolt_databases() -> list[str]:
    """Return list of database aliases that are Dolt databases.

    Results are cached after the first call. Call reset_dolt_databases()
    to clear the cache if needed.

    Returns:
        List of database alias names that are Dolt databases.
    """
    global _dolt_databases
    if _dolt_databases is not None:
        return _dolt_databases

    _dolt_databases = []
    for alias in connections:
        if _is_dolt_database(alias):
            _dolt_databases.append(alias)
    return _dolt_databases


def reset_dolt_databases() -> None:
    """Reset the cached list of Dolt databases.

    Useful for testing or when database configuration changes.
    """
    global _dolt_databases
    _dolt_databases = None


def _is_dolt_database(alias: str) -> bool:
    """Check if a database is a Dolt database.

    Checks the database engine setting to identify MySQL-compatible databases,
    which are assumed to be Dolt when using this package. This avoids querying
    the database during app initialization.

    Args:
        alias: Database alias from Django settings.

    Returns:
        True if the database uses a MySQL-compatible engine, False otherwise.
    """
    from django.conf import settings

    db_settings = settings.DATABASES.get(alias, {})
    engine = db_settings.get("ENGINE", "")
    return "mysql" in engine
