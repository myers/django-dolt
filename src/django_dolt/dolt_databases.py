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

    First checks if it's a MySQL-compatible database, then checks for
    Dolt system tables by attempting to query them directly.

    Args:
        alias: Database alias from Django settings.

    Returns:
        True if the database is a Dolt database, False otherwise.
    """
    try:
        conn = connections[alias]
        # Only check MySQL-compatible databases
        if conn.vendor != "mysql":
            return False

        with conn.cursor() as cursor:
            # Try to query the dolt_branches system table directly
            # SHOW TABLES doesn't show Dolt system tables
            cursor.execute("SELECT 1 FROM dolt_branches LIMIT 1")
            return True
    except Exception:
        return False
