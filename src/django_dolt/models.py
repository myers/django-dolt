"""Django models for Dolt system tables.

These are read-only, unmanaged models that map to Dolt's built-in system tables
for introspection of branches, commits, and remotes.

Module-level ``dolt_*`` functions provide low-level access to Dolt stored
procedures (``CALL DOLT_*``). Business logic and error handling live in
the services layer.
"""

from typing import TYPE_CHECKING, Any, cast

from django.db import connections, models

if TYPE_CHECKING:
    # Type for the tuple of proxy model classes - use Any for dynamic classes
    type ProxyModelTuple = tuple[type[Any], type[Any], type[Any]]


# ---------------------------------------------------------------------------
# Stored-procedure access (no backing table)
# ---------------------------------------------------------------------------


def dolt_add(table: str = ".", *, using: str | None = None) -> None:
    """Execute ``CALL DOLT_ADD(table)``."""
    with connections[using if using is not None else "default"].cursor() as cursor:
        cursor.execute("CALL DOLT_ADD(%s)", [table])


def dolt_commit(
    message: str,
    author: str,
    *,
    allow_empty: bool = False,
    stage_all: bool = False,
    using: str | None = None,
) -> str | None:
    """Execute ``CALL DOLT_COMMIT(...)`` and return the commit hash.

    Returns ``None`` when there is nothing to commit.
    """
    with connections[using if using is not None else "default"].cursor() as cursor:
        args: list[str] = []
        if stage_all:
            args.append("-A")
        args.extend(["-m", message, "--author", author])
        if allow_empty:
            args.append("--allow-empty")

        placeholders = ", ".join(["%s"] * len(args))
        cursor.execute(
            f"CALL DOLT_COMMIT({placeholders})", args  # noqa: S608
        )
        result = cursor.fetchone()
        return str(result[0]) if result else None


def dolt_add_remote(
    name: str, url: str, *, using: str | None = None
) -> None:
    """Execute ``CALL DOLT_REMOTE('add', name, url)``."""
    with connections[using if using is not None else "default"].cursor() as cursor:
        cursor.execute(
            "CALL DOLT_REMOTE('add', %s, %s)", [name, url]
        )


def dolt_push(
    args: list[str], *, using: str | None = None
) -> None:
    """Execute ``CALL DOLT_PUSH(...)``."""
    with connections[using if using is not None else "default"].cursor() as cursor:
        placeholders = ", ".join(["%s"] * len(args))
        cursor.execute(  # noqa: S608
            f"CALL DOLT_PUSH({placeholders})", args
        )


def dolt_pull(
    args: list[str], *, using: str | None = None
) -> tuple[Any, ...] | None:
    """Execute ``CALL DOLT_PULL(...)`` and return the result row."""
    with connections[using if using is not None else "default"].cursor() as cursor:
        placeholders = ", ".join(["%s"] * len(args))
        cursor.execute(  # noqa: S608
            f"CALL DOLT_PULL({placeholders})", args
        )
        result: tuple[Any, ...] | None = cursor.fetchone()
        return result


def dolt_fetch(
    args: list[str], *, using: str | None = None
) -> None:
    """Execute ``CALL DOLT_FETCH(...)``."""
    with connections[using if using is not None else "default"].cursor() as cursor:
        placeholders = ", ".join(["%s"] * len(args))
        cursor.execute(  # noqa: S608
            f"CALL DOLT_FETCH({placeholders})", args
        )


def dolt_diff(
    from_ref: str,
    to_ref: str,
    table: str | None = None,
    *,
    using: str | None = None,
) -> list[dict[str, Any]]:
    """Query ``dolt_diff()`` or ``dolt_diff_summary()``.

    These are table-valued functions with dynamic schemas, so raw
    SQL is required.
    """
    with connections[using if using is not None else "default"].cursor() as cursor:
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


# ---------------------------------------------------------------------------
# Read-only managers
# ---------------------------------------------------------------------------


class BranchManager(models.Manager["Branch"]):
    """Manager for dolt_branches system table."""

    def names(self, *, using: str | None = None) -> list[str]:
        """Return list of branch names."""
        qs = self.using(using) if using else self.all()
        return list(qs.values_list("name", flat=True))

    def active_branch(self, *, using: str | None = None) -> str:
        """Return the currently active branch name.

        Uses the Dolt SQL function ``active_branch()`` which has no
        table equivalent, so raw SQL is required here.
        """
        with connections[using if using is not None else "default"].cursor() as cursor:
            cursor.execute("SELECT active_branch()")
            result = cursor.fetchone()
            return str(result[0]) if result else "main"


class CommitManager(models.Manager["Commit"]):
    """Manager for dolt_log system table."""

    def recent(
        self, limit: int = 50, *, using: str | None = None
    ) -> list[dict[str, Any]]:
        """Return recent commits as dicts.

        Uses ``order_by()`` with no args to preserve Dolt's native
        graph ordering (parent-child) from the ``dolt_log`` table.
        """
        qs = self.using(using) if using else self.all()
        return cast(
            list[dict[str, Any]],
            list(
                qs.order_by().values(
                    "commit_hash", "committer", "email",
                    "date", "message",
                )[:limit]
            ),
        )


class StatusManager(models.Manager["Status"]):
    """Manager for dolt_status system table."""

    def current(
        self,
        exclude_ignored: bool = True,
        *,
        using: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return current working-set status rows.

        When ``exclude_ignored`` is True, a ``NOT EXISTS`` subquery
        with ``LIKE`` matching against ``dolt_ignore`` is used, which
        cannot be cleanly expressed in the ORM, so raw SQL is required.
        """
        if not exclude_ignored:
            qs = self.using(using) if using else self.all()
            return cast(
                list[dict[str, Any]],
                list(qs.values("table_name", "staged", "status")),
            )

        with connections[using if using is not None else "default"].cursor() as cursor:
            cursor.execute("""
                SELECT s.* FROM dolt_status s
                WHERE NOT EXISTS (
                    SELECT 1 FROM dolt_ignore i
                    WHERE i.ignored = 1
                    AND s.table_name LIKE i.pattern
                )
            """)
            columns = [
                col[0] for col in cursor.description or []
            ]
            return [
                dict(zip(columns, row, strict=False))
                for row in cursor.fetchall()
            ]


class IgnoreManager(models.Manager["Ignore"]):
    """Manager for dolt_ignore system table."""

    def patterns(self, *, using: str | None = None) -> list[str]:
        """Return ignored table patterns."""
        qs = self.using(using) if using else self.all()
        return list(
            qs.filter(ignored=True).values_list("pattern", flat=True)
        )


class RemoteManager(models.Manager["Remote"]):
    """Manager for dolt_remotes system table."""

    def all_remotes(
        self, *, using: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all remotes as dicts."""
        qs = self.using(using) if using else self.all()
        return cast(list[dict[str, Any]], list(qs.values()))


# ---------------------------------------------------------------------------
# Model definitions
# ---------------------------------------------------------------------------


class Branch(models.Model):
    """Read-only model for dolt_branches system table."""

    name = models.CharField(max_length=255, primary_key=True)
    hash = models.CharField(max_length=64)
    latest_committer = models.CharField(max_length=255)
    latest_committer_email = models.CharField(max_length=255)
    latest_commit_date = models.DateTimeField()
    latest_commit_message = models.TextField()

    objects = BranchManager()

    class Meta:
        managed = False
        db_table = "dolt_branches"
        verbose_name = "Branch"
        verbose_name_plural = "Branches"

    def __str__(self) -> str:
        return self.name


class Commit(models.Model):
    """Read-only model for dolt_log system table."""

    commit_hash = models.CharField(max_length=64, primary_key=True)
    committer = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    date = models.DateTimeField()
    message = models.TextField()

    objects = CommitManager()

    class Meta:
        managed = False
        db_table = "dolt_log"
        verbose_name = "Commit"
        verbose_name_plural = "Commits"

    def __str__(self) -> str:
        return f"{self.commit_hash[:8]} - {self.message[:50]}"


class Status(models.Model):
    """Read-only model for dolt_status system table."""

    table_name = models.CharField(max_length=255, primary_key=True)
    staged = models.BooleanField()
    status = models.CharField(max_length=64)

    objects = StatusManager()

    class Meta:
        managed = False
        db_table = "dolt_status"
        verbose_name = "Status"
        verbose_name_plural = "Status"


class Ignore(models.Model):
    """Read-only model for dolt_ignore system table."""

    pattern = models.CharField(max_length=255, primary_key=True)
    ignored = models.BooleanField()

    objects = IgnoreManager()

    class Meta:
        managed = False
        db_table = "dolt_ignore"
        verbose_name = "Ignore Rule"
        verbose_name_plural = "Ignore Rules"


class Remote(models.Model):
    """Read-only model for dolt_remotes system table."""

    name = models.CharField(max_length=255, primary_key=True)
    url = models.CharField(max_length=1024)
    fetch_specs = models.JSONField(null=True)
    params = models.JSONField(null=True)

    objects = RemoteManager()

    class Meta:
        managed = False
        db_table = "dolt_remotes"
        verbose_name = "Remote"
        verbose_name_plural = "Remotes"

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Dynamic proxy model factory
# ---------------------------------------------------------------------------

_proxy_model_registry: dict[str, "ProxyModelTuple"] = {}


def create_proxy_models(db_alias: str) -> "ProxyModelTuple":
    """Create proxy models for a specific database.

    Creates database-specific proxy models that can be registered separately
    in Django admin. Each proxy model has a _database attribute indicating
    which database it should query.

    Args:
        db_alias: Database alias from Django settings.

    Returns:
        Tuple of (BranchProxy, CommitProxy, RemoteProxy) model classes.
    """
    # Return cached models if already created
    if db_alias in _proxy_model_registry:
        return _proxy_model_registry[db_alias]

    # Create unique class names to avoid conflicts
    class_suffix = db_alias.replace("-", "_").replace(".", "_")

    # Format db_alias for display (e.g., "inventory_db" -> "Inventory Db")
    display_name = db_alias.replace("_", " ").title()

    # Use type() to create classes with unique names from the start
    # This avoids Django's model registration conflict
    BranchProxy = type(
        f"Branch_{class_suffix}",
        (Branch,),
        {
            "_database": db_alias,
            "__module__": "django_dolt.models",
            "Meta": type(
                "Meta",
                (),
                {
                    "proxy": True,
                    "app_label": "django_dolt",
                    "verbose_name": f"Branch ({display_name})",
                    "verbose_name_plural": f"Branches ({display_name})",
                },
            ),
        },
    )

    CommitProxy = type(
        f"Commit_{class_suffix}",
        (Commit,),
        {
            "_database": db_alias,
            "__module__": "django_dolt.models",
            "Meta": type(
                "Meta",
                (),
                {
                    "proxy": True,
                    "app_label": "django_dolt",
                    "verbose_name": f"Commit ({display_name})",
                    "verbose_name_plural": f"Commits ({display_name})",
                },
            ),
        },
    )

    RemoteProxy = type(
        f"Remote_{class_suffix}",
        (Remote,),
        {
            "_database": db_alias,
            "__module__": "django_dolt.models",
            "Meta": type(
                "Meta",
                (),
                {
                    "proxy": True,
                    "app_label": "django_dolt",
                    "verbose_name": f"Remote ({display_name})",
                    "verbose_name_plural": f"Remotes ({display_name})",
                },
            ),
        },
    )

    result = (BranchProxy, CommitProxy, RemoteProxy)
    _proxy_model_registry[db_alias] = result
    return result


def reset_proxy_model_registry() -> None:
    """Clear the proxy model registry. Intended for testing only."""
    _proxy_model_registry.clear()


def get_proxy_models(db_alias: str) -> "ProxyModelTuple | None":
    """Get previously created proxy models for a database.

    Args:
        db_alias: Database alias from Django settings.

    Returns:
        Tuple of proxy model classes, or None if not created yet.
    """
    return _proxy_model_registry.get(db_alias)
