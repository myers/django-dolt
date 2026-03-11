"""
Dolt database operations service.

Business logic for Dolt version control features. All database access
is delegated to model managers and functions in
``django_dolt.models``.
"""

import os
from typing import Any


class DoltError(Exception):
    """Base exception for Dolt operations."""


class DoltCommitError(DoltError):
    """Raised when a Dolt commit fails."""


class DoltPushError(DoltError):
    """Raised when a Dolt push fails."""


class DoltPullError(DoltError):
    """Raised when a Dolt pull fails."""


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


def dolt_add(table: str = ".", *, using: str | None = None) -> None:
    """Stage table(s) for commit.

    Raises:
        DoltError: If the add operation fails
    """
    from django_dolt import models

    try:
        models.dolt_add(table, using=using)
    except Exception as e:
        raise DoltError(f"Failed to stage '{table}': {e}") from e


def dolt_commit(
    message: str,
    author: str = "Django <django@localhost>",
    allow_empty: bool = False,
    *,
    using: str | None = None,
) -> str | None:
    """Commit staged changes to Dolt.

    Returns:
        Commit hash if successful, None if no changes

    Raises:
        DoltCommitError: If the commit fails
    """
    from django_dolt import models

    try:
        return models.dolt_commit(
            message, author, allow_empty=allow_empty, using=using
        )
    except Exception as e:
        if "nothing to commit" in str(e).lower():
            return None
        raise DoltCommitError(f"Failed to commit: {e}") from e


def dolt_add_and_commit(
    message: str,
    table: str = ".",
    author: str = "Django <django@localhost>",
    *,
    using: str | None = None,
) -> str | None:
    """Stage and commit changes in a single atomic operation.

    Uses ``DOLT_COMMIT('-A', ...)`` to stage all tables (including new
    ones) and commit in one call, avoiding race conditions between
    separate add and commit steps.

    When *table* is not ``"."``, falls back to an explicit
    ``dolt_add`` + ``dolt_commit`` pair for that specific table.
    """
    from django_dolt import models

    if table != ".":
        dolt_add(table, using=using)
        return dolt_commit(message, author, using=using)

    try:
        return models.dolt_commit(
            message, author, stage_all=True, using=using
        )
    except Exception as e:
        if "nothing to commit" in str(e).lower():
            return None
        raise DoltCommitError(f"Failed to commit: {e}") from e


def dolt_add_remote(
    name: str, url: str, *, using: str | None = None
) -> None:
    """Add a remote repository.

    Raises:
        DoltError: If adding the remote fails
    """
    from django_dolt import models

    try:
        models.dolt_add_remote(name, url, using=using)
    except Exception as e:
        raise DoltError(
            f"Failed to add remote '{name}': {e}"
        ) from e


def dolt_push(
    remote: str = "origin",
    branch: str = "main",
    force: bool = False,
    user: str | None = None,
    *,
    using: str | None = None,
) -> str:
    """Push changes to remote repository.

    Raises:
        DoltPushError: If push fails
    """
    from django_dolt import models

    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    try:
        push_args: list[str] = []
        if user:
            push_args.extend(["--user", user])
        if force:
            push_args.append("--force")
        push_args.extend([remote, branch])

        models.dolt_push(push_args, using=using)
        return f"Pushed {branch} to {remote}"
    except Exception as e:
        error_msg = str(e)
        if "DOLT_REMOTE_PASSWORD" in error_msg:
            raise DoltPushError(
                f"Push failed: {error_msg}\n"
                "Note: DOLT_PUSH requires the "
                "DOLT_REMOTE_PASSWORD environment "
                "variable to be set at the Dolt server level."
            ) from e
        raise DoltPushError(f"Push failed: {error_msg}") from e


def dolt_pull(
    remote: str = "origin",
    branch: str | None = None,
    user: str | None = None,
    *,
    using: str | None = None,
) -> str:
    """Pull changes from remote repository.

    Raises:
        DoltPullError: If pull fails
    """
    from django_dolt import models

    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    if branch is None:
        branch = dolt_current_branch(using=using)

    try:
        pull_args: list[str] = []
        if user:
            pull_args.extend(["--user", user])
        pull_args.extend([remote, branch])

        result = models.dolt_pull(pull_args, using=using)
        if result:
            fast_forward = result[0]
            conflicts = result[1] if len(result) > 1 else 0
            if conflicts:
                return f"Pulled with {conflicts} conflicts"
            if fast_forward:
                return "Fast-forward pull successful"
            return "Already up to date"
        return "Pull completed"
    except Exception as e:
        raise DoltPullError(f"Pull failed: {e}") from e


def dolt_fetch(
    remote: str = "origin",
    user: str | None = None,
    *,
    using: str | None = None,
) -> str:
    """Fetch changes from remote without merging.

    Raises:
        DoltError: If fetch fails
    """
    from django_dolt import models

    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    try:
        fetch_args: list[str] = []
        if user:
            fetch_args.extend(["--user", user])
        fetch_args.append(remote)

        models.dolt_fetch(fetch_args, using=using)
        return f"Fetched from {remote}"
    except Exception as e:
        raise DoltError(f"Fetch failed: {e}") from e


# ---------------------------------------------------------------------------
# Read operations — thin wrappers around model managers
# ---------------------------------------------------------------------------


def dolt_status(
    exclude_ignored: bool = True, *, using: str | None = None
) -> list[dict[str, Any]]:
    """Get the current Dolt working set status.

    Raises:
        DoltError: If the status query fails
    """
    from django_dolt import models

    try:
        return models.Status.objects.current(
            exclude_ignored=exclude_ignored, using=using
        )
    except Exception as e:
        raise DoltError(f"Failed to get status: {e}") from e


def dolt_log(
    limit: int = 50, *, using: str | None = None
) -> list[dict[str, Any]]:
    """Get recent commit history."""
    from django_dolt import models

    return models.Commit.objects.recent(limit=limit, using=using)


def dolt_diff(
    from_ref: str = "HEAD",
    to_ref: str = "WORKING",
    table: str | None = None,
    *,
    using: str | None = None,
) -> list[dict[str, Any]]:
    """Get diff between two refs."""
    from django_dolt import models

    return models.dolt_diff(from_ref, to_ref, table, using=using)


def dolt_branch_list(
    *, using: str | None = None
) -> list[str]:
    """Get list of branch names."""
    from django_dolt import models

    return models.Branch.objects.names(using=using)


def dolt_current_branch(
    *, using: str | None = None
) -> str:
    """Get the current branch name."""
    from django_dolt import models

    return models.Branch.objects.active_branch(using=using)


def get_ignored_tables(
    *, using: str | None = None
) -> list[str]:
    """Get list of ignored table patterns from dolt_ignore."""
    from django_dolt import models

    return models.Ignore.objects.patterns(using=using)


def dolt_remotes(
    *, using: str | None = None
) -> list[dict[str, Any]]:
    """Get list of configured remotes."""
    from django_dolt import models

    return models.Remote.objects.all_remotes(using=using)


# ---------------------------------------------------------------------------
# Formatting utility
# ---------------------------------------------------------------------------


def format_status_rows(
    status_rows: list[dict[str, Any]],
) -> str:
    """Format dolt_status output for display."""
    if not status_rows:
        return "No changes"

    output = []
    for row in status_rows:
        staged = (
            "staged" if row.get("staged", 0) else "modified"
        )
        table = row.get("table_name", "unknown")
        status = row.get("status", "")
        output.append(f"  {staged}: {table} ({status})")
    return "\n".join(output)
