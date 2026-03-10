"""Django integration for Dolt version-controlled databases."""

from typing import Any

# Eagerly import service-layer functions since they don't depend on
# Django's app registry being ready.
from django_dolt.decorators import dolt_autocommit, get_author_from_request
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
    format_status_rows,
    get_ignored_tables,
)

__version__ = "1.0.0"
__all__ = [
    # Models (lazy-loaded to avoid AppRegistryNotReady)
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
    "format_status_rows",
    "get_dolt_databases",
    # View decorator
    "dolt_autocommit",
    "get_author_from_request",
    # Admin extension
    "register_branch_extension",
    "DoltCommitMixin",
]


def __getattr__(name: str) -> Any:
    """Lazy import for models and admin classes to avoid AppRegistryNotReady errors."""
    if name in ("Branch", "Commit", "Remote"):
        from django.apps import apps

        return apps.get_model("django_dolt", name)
    if name == "get_dolt_databases":
        from django_dolt.dolt_databases import get_dolt_databases

        return get_dolt_databases
    if name == "register_branch_extension":
        from django_dolt.admin import register_branch_extension

        return register_branch_extension
    if name == "DoltCommitMixin":
        from django_dolt.admin import DoltCommitMixin

        return DoltCommitMixin
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
