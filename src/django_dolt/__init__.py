"""Django integration for Dolt version-controlled databases."""

from __future__ import annotations

from typing import Any

from django_dolt.services import (
    DoltCommitError,
    DoltError,
    DoltPullError,
    DoltPushError,
    dolt_add,
    dolt_add_and_commit,
    dolt_add_remote,
    dolt_branch_list,
    dolt_commit,
    dolt_current_branch,
    dolt_diff,
    dolt_fetch,
    dolt_log,
    dolt_pull,
    dolt_push,
    dolt_remotes,
    dolt_status,
    get_ignored_tables,
)

__version__ = "0.1.0"
__all__ = [
    # Models (lazy-loaded)
    "Branch",
    "Commit",
    "Remote",
    # Exceptions
    "DoltError",
    "DoltCommitError",
    "DoltPushError",
    "DoltPullError",
    # Core operations
    "dolt_add",
    "dolt_commit",
    "dolt_add_and_commit",
    "dolt_status",
    "dolt_log",
    "dolt_diff",
    "dolt_pull",
    "dolt_push",
    "dolt_fetch",
    # Branch operations
    "dolt_branch_list",
    "dolt_current_branch",
    # Remote operations
    "dolt_remotes",
    "dolt_add_remote",
    # Utilities
    "get_ignored_tables",
    "get_dolt_databases",
]


def __getattr__(name: str) -> Any:
    """Lazy import for models and utilities to avoid AppRegistryNotReady errors."""
    if name in ("Branch", "Commit", "Remote"):
        from django.apps import apps

        return apps.get_model("django_dolt", name)
    if name == "get_dolt_databases":
        from django_dolt.dolt_databases import get_dolt_databases

        return get_dolt_databases
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


default_app_config = "django_dolt.apps.DjangoDoltConfig"
