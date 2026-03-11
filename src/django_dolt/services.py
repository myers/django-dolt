"""
Dolt database operations service.

Provides functions for interacting with Dolt version control features
via Django's database connection. Read queries are delegated to model
managers; write operations (CALL DOLT_*) live here.
"""

import os
from typing import Any

from django.db import connection, connections


def _get_connection(using: str | None = None) -> Any:
    """Get database connection for the specified alias."""
    if using is None:
        return connection
    return connections[using]


class DoltError(Exception):
    """Base exception for Dolt operations."""


class DoltCommitError(DoltError):
    """Raised when a Dolt commit fails."""


class DoltPushError(DoltError):
    """Raised when a Dolt push fails."""


class DoltPullError(DoltError):
    """Raised when a Dolt pull fails."""


# ---------------------------------------------------------------------------
# Write operations (stored procedures)
# ---------------------------------------------------------------------------


def dolt_add(table: str = ".", *, using: str | None = None) -> None:
    """Stage table(s) for commit.

    Raises:
        DoltError: If the add operation fails
    """
    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            cursor.execute("CALL DOLT_ADD(%s)", [table])
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
    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            if allow_empty:
                cursor.execute(
                    "CALL DOLT_COMMIT("
                    "'-m', %s, '--author', %s, '--allow-empty')",
                    [message, author],
                )
            else:
                cursor.execute(
                    "CALL DOLT_COMMIT('-m', %s, '--author', %s)",
                    [message, author],
                )
            result = cursor.fetchone()
            return str(result[0]) if result else None
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
    """Stage and commit changes in one operation."""
    dolt_add(table, using=using)
    return dolt_commit(message, author, using=using)


def dolt_add_remote(
    name: str, url: str, *, using: str | None = None
) -> None:
    """Add a remote repository.

    Raises:
        DoltError: If adding the remote fails
    """
    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            cursor.execute(
                "CALL DOLT_REMOTE('add', %s, %s)", [name, url]
            )
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
    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            push_args: list[str] = []
            if user:
                push_args.extend(["--user", user])
            if force:
                push_args.append("--force")
            push_args.extend([remote, branch])

            placeholders = ", ".join(["%s"] * len(push_args))
            cursor.execute(  # noqa: S608
                f"CALL DOLT_PUSH({placeholders})", push_args
            )

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
    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    if branch is None:
        branch = dolt_current_branch(using=using)

    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            pull_args: list[str] = []
            if user:
                pull_args.extend(["--user", user])
            pull_args.extend([remote, branch])

            placeholders = ", ".join(["%s"] * len(pull_args))
            cursor.execute(  # noqa: S608
                f"CALL DOLT_PULL({placeholders})", pull_args
            )
            result = cursor.fetchone()
            if result:
                fast_forward = result[0]
                conflicts = (
                    result[1] if len(result) > 1 else 0
                )
                if conflicts:
                    return (
                        f"Pulled with {conflicts} conflicts"
                    )
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
    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    try:
        conn = _get_connection(using)
        with conn.cursor() as cursor:
            fetch_args: list[str] = []
            if user:
                fetch_args.extend(["--user", user])
            fetch_args.append(remote)

            placeholders = ", ".join(["%s"] * len(fetch_args))
            cursor.execute(  # noqa: S608
                f"CALL DOLT_FETCH({placeholders})", fetch_args
            )
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
    from django_dolt.models import Status

    return Status.objects.current(
        exclude_ignored=exclude_ignored, using=using
    )


def dolt_log(
    limit: int = 50, *, using: str | None = None
) -> list[dict[str, Any]]:
    """Get recent commit history."""
    from django_dolt.models import Commit

    return Commit.objects.recent(limit=limit, using=using)


def dolt_diff(
    from_ref: str = "HEAD",
    to_ref: str = "WORKING",
    table: str | None = None,
    *,
    using: str | None = None,
) -> list[dict[str, Any]]:
    """Get diff between two refs.

    Uses dolt_diff() / dolt_diff_summary() table-valued functions
    which have no fixed schema, so raw SQL stays here.
    """
    conn = _get_connection(using)
    with conn.cursor() as cursor:
        if table:
            cursor.execute(
                "SELECT * FROM dolt_diff(%s, %s, %s)",
                [from_ref, to_ref, table],
            )
        else:
            cursor.execute(
                "SELECT * FROM dolt_diff_summary(%s, %s)",
                [from_ref, to_ref],
            )
        columns = [
            col[0] for col in cursor.description or []
        ]
        return [
            dict(zip(columns, row, strict=False))
            for row in cursor.fetchall()
        ]


def dolt_branch_list(
    *, using: str | None = None
) -> list[str]:
    """Get list of branch names."""
    from django_dolt.models import Branch

    return Branch.objects.names(using=using)


def dolt_current_branch(
    *, using: str | None = None
) -> str:
    """Get the current branch name."""
    from django_dolt.models import Branch

    return Branch.objects.active_branch(using=using)


def get_ignored_tables(
    *, using: str | None = None
) -> list[str]:
    """Get list of ignored table patterns from dolt_ignore."""
    from django_dolt.models import Ignore

    return Ignore.objects.patterns(using=using)


def dolt_remotes(
    *, using: str | None = None
) -> list[dict[str, Any]]:
    """Get list of configured remotes."""
    from django_dolt.models import Remote

    return Remote.objects.all_remotes(using=using)


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
