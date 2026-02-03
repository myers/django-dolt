"""
Dolt database operations service.

Provides functions for interacting with Dolt version control features
via Django's database connection.
"""

from __future__ import annotations

import os
from typing import Any

from django.db import connection


class DoltError(Exception):
    """Base exception for Dolt operations."""


class DoltCommitError(DoltError):
    """Raised when a Dolt commit fails."""


class DoltPushError(DoltError):
    """Raised when a Dolt push fails."""


class DoltPullError(DoltError):
    """Raised when a Dolt pull fails."""


def dolt_add(table: str = ".") -> None:
    """Stage table(s) for commit.

    Args:
        table: Table name to stage, or "." for all tables (default: ".")

    Raises:
        DoltError: If the add operation fails
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("CALL DOLT_ADD(%s)", [table])
    except Exception as e:
        raise DoltError(f"Failed to stage '{table}': {e}") from e


def dolt_commit(
    message: str,
    author: str = "Django <django@localhost>",
    allow_empty: bool = False,
) -> str | None:
    """Commit staged changes to Dolt.

    Args:
        message: Commit message
        author: Author string in "Name <email>" format
        allow_empty: If True, allow commits with no changes

    Returns:
        Commit hash if successful, None if no changes and allow_empty=False

    Raises:
        DoltCommitError: If the commit fails
    """
    try:
        with connection.cursor() as cursor:
            if allow_empty:
                cursor.execute(
                    "CALL DOLT_COMMIT('-m', %s, '--author', %s, '--allow-empty')",
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
) -> str | None:
    """Stage and commit changes in one operation.

    Args:
        message: Commit message
        table: Table name to stage, or "." for all tables
        author: Author string in "Name <email>" format

    Returns:
        Commit hash if successful, None if no changes

    Raises:
        DoltError: If staging fails
        DoltCommitError: If commit fails
    """
    dolt_add(table)
    return dolt_commit(message, author)


def dolt_status(exclude_ignored: bool = True) -> list[dict[str, Any]]:
    """Get the current Dolt working set status.

    Args:
        exclude_ignored: If True, filter out tables matching dolt_ignore patterns

    Returns:
        List of dicts with table_name, staged, and status fields
    """
    with connection.cursor() as cursor:
        if exclude_ignored:
            cursor.execute("""
                SELECT s.* FROM dolt_status s
                WHERE NOT EXISTS (
                    SELECT 1 FROM dolt_ignore i
                    WHERE i.ignored = 1
                    AND s.table_name LIKE i.pattern
                )
            """)
        else:
            cursor.execute("SELECT * FROM dolt_status")
        columns = [col[0] for col in cursor.description or []]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def dolt_log(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent commit history.

    Args:
        limit: Maximum number of commits to return

    Returns:
        List of dicts with commit_hash, committer, email, date, message fields
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT commit_hash, committer, email, date, message "
            "FROM dolt_log LIMIT %s",
            [limit],
        )
        columns = [col[0] for col in cursor.description or []]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def dolt_diff(
    from_ref: str = "HEAD",
    to_ref: str = "WORKING",
    table: str | None = None,
) -> list[dict[str, Any]]:
    """Get diff between two refs.

    Args:
        from_ref: Starting ref (commit hash, branch, or "HEAD")
        to_ref: Ending ref (commit hash, branch, or "WORKING")
        table: Optional table name to filter diff

    Returns:
        List of dicts representing diff rows
    """
    with connection.cursor() as cursor:
        if table:
            cursor.execute(
                f"SELECT * FROM dolt_diff('{from_ref}', '{to_ref}', '{table}')"  # noqa: S608
            )
        else:
            cursor.execute(
                "SELECT * FROM dolt_diff_summary(%s, %s)",
                [from_ref, to_ref],
            )
        columns = [col[0] for col in cursor.description or []]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def dolt_branch_list() -> list[str]:
    """Get list of branches.

    Returns:
        List of branch names
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM dolt_branches")
        return [str(row[0]) for row in cursor.fetchall()]


def dolt_current_branch() -> str:
    """Get the current branch name.

    Returns:
        Current branch name
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT active_branch()")
        result = cursor.fetchone()
        return str(result[0]) if result else "main"


def get_ignored_tables() -> list[str]:
    """Get list of ignored table patterns from dolt_ignore.

    Returns:
        List of table name patterns that are ignored
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pattern FROM dolt_ignore WHERE ignored = 1")
        return [str(row[0]) for row in cursor.fetchall()]


def dolt_remotes() -> list[dict[str, Any]]:
    """Get list of configured remotes.

    Returns:
        List of dicts with name, url, and other remote info
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM dolt_remotes")
        columns = [col[0] for col in cursor.description or []]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def dolt_add_remote(name: str, url: str) -> None:
    """Add a remote repository.

    Args:
        name: Remote name (e.g., "origin")
        url: Remote URL

    Raises:
        DoltError: If adding the remote fails
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("CALL DOLT_REMOTE('add', %s, %s)", [name, url])
    except Exception as e:
        raise DoltError(f"Failed to add remote '{name}': {e}") from e


def dolt_push(
    remote: str = "origin",
    branch: str = "main",
    force: bool = False,
    user: str | None = None,
) -> str:
    """Push changes to remote repository.

    Args:
        remote: Remote name (default: "origin")
        branch: Branch to push (default: "main")
        force: Force push (default: False)
        user: Remote username for authentication

    Returns:
        Success message

    Raises:
        DoltPushError: If push fails
    """
    if user is None:
        user = os.environ.get("DOLT_REMOTE_USER", "")

    try:
        with connection.cursor() as cursor:
            push_args: list[str] = []
            if user:
                push_args.extend(["--user", user])
            if force:
                push_args.append("--force")
            push_args.extend([remote, branch])

            placeholders = ", ".join(["%s"] * len(push_args))
            cursor.execute(f"CALL DOLT_PUSH({placeholders})", push_args)  # noqa: S608

            return f"Pushed {branch} to {remote}"
    except Exception as e:
        error_msg = str(e)
        if "DOLT_REMOTE_PASSWORD" in error_msg:
            raise DoltPushError(
                f"Push failed: {error_msg}\n"
                "Note: DOLT_PUSH requires the DOLT_REMOTE_PASSWORD environment "
                "variable to be set at the Dolt server level."
            ) from e
        raise DoltPushError(f"Push failed: {error_msg}") from e


def dolt_pull(
    remote: str = "origin",
    branch: str | None = None,
) -> str:
    """Pull changes from remote repository.

    Args:
        remote: Remote name (default: "origin")
        branch: Branch to pull (default: current branch)

    Returns:
        Pull result message

    Raises:
        DoltPullError: If pull fails
    """
    if branch is None:
        branch = dolt_current_branch()

    try:
        with connection.cursor() as cursor:
            cursor.execute("CALL DOLT_PULL(%s, %s)", [remote, branch])
            result = cursor.fetchone()
            # dolt_pull returns (fast_forward, conflicts, message)
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


def dolt_fetch(remote: str = "origin") -> str:
    """Fetch changes from remote without merging.

    Args:
        remote: Remote name (default: "origin")

    Returns:
        Fetch result message

    Raises:
        DoltError: If fetch fails
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("CALL DOLT_FETCH(%s)", [remote])
            return f"Fetched from {remote}"
    except Exception as e:
        raise DoltError(f"Fetch failed: {e}") from e
