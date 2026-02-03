"""Django models for Dolt system tables.

These are read-only, unmanaged models that map to Dolt's built-in system tables
for introspection of branches, commits, and remotes.
"""

from __future__ import annotations

from django.db import models


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
