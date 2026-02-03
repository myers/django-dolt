"""Django models for Dolt system tables.

These are read-only, unmanaged models that map to Dolt's built-in system tables
for introspection of branches, commits, and remotes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from typing import Any

    # Type for the tuple of proxy model classes - use Any for dynamic classes
    type ProxyModelTuple = tuple[type[Any], type[Any], type[Any]]


class Branch(models.Model):
    """Read-only model for dolt_branches system table."""

    name = models.CharField(max_length=255, primary_key=True)
    hash = models.CharField(max_length=64)
    latest_committer = models.CharField(max_length=255)
    latest_committer_email = models.CharField(max_length=255)
    latest_commit_date = models.DateTimeField()
    latest_commit_message = models.TextField()

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

    class Meta:
        managed = False
        db_table = "dolt_log"
        verbose_name = "Commit"
        verbose_name_plural = "Commits"

    def __str__(self) -> str:
        return f"{self.commit_hash[:8]} - {self.message[:50]}"


class Remote(models.Model):
    """Read-only model for dolt_remotes system table."""

    name = models.CharField(max_length=255, primary_key=True)
    url = models.CharField(max_length=1024)
    fetch_specs = models.JSONField(null=True)
    params = models.JSONField(null=True)

    class Meta:
        managed = False
        db_table = "dolt_remotes"
        verbose_name = "Remote"
        verbose_name_plural = "Remotes"

    def __str__(self) -> str:
        return self.name


# Registry for dynamically created proxy models
_proxy_model_registry: dict[str, ProxyModelTuple] = {}


def create_proxy_models(db_alias: str) -> ProxyModelTuple:
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


def get_proxy_models(db_alias: str) -> ProxyModelTuple | None:
    """Get previously created proxy models for a database.

    Args:
        db_alias: Database alias from Django settings.

    Returns:
        Tuple of proxy model classes, or None if not created yet.
    """
    return _proxy_model_registry.get(db_alias)
