"""Dolt database discovery.

Provides utilities for determining which configured Django databases are Dolt databases.
"""

_dolt_databases: list[str] | None = None


def get_dolt_databases() -> list[str]:
    """Return list of database aliases that are Dolt databases.

    Reads from the ``DOLT_DATABASES`` Django setting. If the setting is
    missing or empty, returns an empty list.

    Results are cached after the first call. Call reset_dolt_databases()
    to clear the cache if needed.

    Returns:
        List of database alias names that are Dolt databases.
    """
    global _dolt_databases
    if _dolt_databases is not None:
        return _dolt_databases
    from django.conf import settings

    _dolt_databases = list(getattr(settings, "DOLT_DATABASES", []))
    return _dolt_databases


def reset_dolt_databases() -> None:
    """Reset the cached list of Dolt databases.

    Useful for testing or when database configuration changes.
    """
    global _dolt_databases
    _dolt_databases = None
