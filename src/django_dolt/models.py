"""Django models for Dolt system tables.

These are read-only, unmanaged models that map to Dolt's built-in system tables
for introspection of branches, commits, and remotes.
"""

from typing import TYPE_CHECKING, Any

from django.db import connection as default_connection
from django.db import connections, models

if TYPE_CHECKING:
    # Type for the tuple of proxy model classes - use Any for dynamic classes
    type ProxyModelTuple = tuple[type[Any], type[Any], type[Any]]


def _conn(using: str | None = None) -> Any:
    if using is None:
        return default_connection
    return connections[using]


class BranchManager(models.Manager["Branch"]):
    """Manager for dolt_branches system table."""

    def names(self, *, using: str | None = None) -> list[str]:
        """Return list of branch names."""
        qs = self.using(using) if using else self.all()
        return list(qs.values_list("name", flat=True))

    def active_branch(self, *, using: str | None = None) -> str:
        """Return the currently active branch name."""
        conn = _conn(using)
        with conn.cursor() as cursor:
            cursor.execute("SELECT active_branch()")
            result = cursor.fetchone()
            return str(result[0]) if result else "main"


class CommitManager(models.Manager["Commit"]):
    """Manager for dolt_log system table."""

    def recent(
        self, limit: int = 50, *, using: str | None = None
    ) -> list[dict[str, Any]]:
        """Return recent commits as dicts."""
        conn = _conn(using)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT commit_hash, committer, email, "
                "date, message FROM dolt_log LIMIT %s",
                [limit],
            )
            columns = [
                col[0] for col in cursor.description or []
            ]
            return [
                dict(zip(columns, row, strict=False))
                for row in cursor.fetchall()
            ]


class StatusManager(models.Manager["Status"]):
    """Manager for dolt_status system table."""

    def current(
        self,
        exclude_ignored: bool = True,
        *,
        using: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return current working-set status rows."""
        from django_dolt.services import DoltError

        try:
            conn = _conn(using)
            with conn.cursor() as cursor:
                if exclude_ignored:
                    try:
                        cursor.execute("""
                            SELECT s.* FROM dolt_status s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM dolt_ignore i
                                WHERE i.ignored = 1
                                AND s.table_name LIKE i.pattern
                            )
                        """)
                    except Exception:
                        cursor.execute(
                            "SELECT * FROM dolt_status"
                        )
                else:
                    cursor.execute("SELECT * FROM dolt_status")
                columns = [
                    col[0] for col in cursor.description or []
                ]
                return [
                    dict(zip(columns, row, strict=False))
                    for row in cursor.fetchall()
                ]
        except DoltError:
            raise
        except Exception as e:
            raise DoltError(
                f"Failed to get status: {e}"
            ) from e


class IgnoreManager(models.Manager["Ignore"]):
    """Manager for dolt_ignore system table."""

    def patterns(self, *, using: str | None = None) -> list[str]:
        """Return ignored table patterns."""
        conn = _conn(using)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pattern FROM dolt_ignore WHERE ignored = 1"
            )
            return [str(row[0]) for row in cursor.fetchall()]


class RemoteManager(models.Manager["Remote"]):
    """Manager for dolt_remotes system table."""

    def all_remotes(
        self, *, using: str | None = None
    ) -> list[dict[str, Any]]:
        """Return all remotes as dicts."""
        conn = _conn(using)
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM dolt_remotes")
            columns = [
                col[0] for col in cursor.description or []
            ]
            return [
                dict(zip(columns, row, strict=False))
                for row in cursor.fetchall()
            ]


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


# Registry for dynamically created proxy models
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


def get_proxy_models(db_alias: str) -> "ProxyModelTuple | None":
    """Get previously created proxy models for a database.

    Args:
        db_alias: Database alias from Django settings.

    Returns:
        Tuple of proxy model classes, or None if not created yet.
    """
    return _proxy_model_registry.get(db_alias)
