"""Django integration for Dolt version-controlled databases."""

from django_dolt.services import (
    DoltCommitError,
    DoltError,
    DoltPullError,
    DoltPushError,
    dolt_add,
    dolt_add_and_commit,
    dolt_branch_list,
    dolt_commit,
    dolt_current_branch,
    dolt_diff,
    dolt_log,
    dolt_pull,
    dolt_push,
    dolt_status,
    get_ignored_tables,
)

__version__ = "0.1.0"
__all__ = [
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
    # Branch operations
    "dolt_branch_list",
    "dolt_current_branch",
    # Utilities
    "get_ignored_tables",
]

default_app_config = "django_dolt.apps.DjangoDoltConfig"
