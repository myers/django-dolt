"""Tests for multi-database support."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from django.db import connections

from django_dolt.dolt_databases import (
    get_dolt_databases,
    reset_dolt_databases,
)
from django_dolt.models import create_proxy_models, get_proxy_models
from django_dolt.services import (
    dolt_add,
    dolt_branch_list,
    dolt_commit,
    dolt_current_branch,
    dolt_log,
    dolt_status,
)


class TestDoltDatabaseDiscovery:
    """Tests for Dolt database discovery via DOLT_DATABASES setting."""

    def setup_method(self) -> None:
        reset_dolt_databases()

    def teardown_method(self) -> None:
        reset_dolt_databases()

    def test_get_dolt_databases_reads_setting(self) -> None:
        with patch("django.conf.settings.DOLT_DATABASES", ["mydb1", "mydb2"]):
            result = get_dolt_databases()
            assert result == ["mydb1", "mydb2"]

    def test_get_dolt_databases_caches_result(self) -> None:
        with patch("django.conf.settings.DOLT_DATABASES", ["db1"]):
            result1 = get_dolt_databases()
            result2 = get_dolt_databases()
            assert result1 is result2

    def test_reset_dolt_databases_clears_cache(self) -> None:
        with patch("django.conf.settings.DOLT_DATABASES", ["db1"]):
            result1 = get_dolt_databases()
            reset_dolt_databases()
            result2 = get_dolt_databases()
            assert result1 is not result2

    def test_get_dolt_databases_missing_setting(self) -> None:
        """When DOLT_DATABASES is not set, return empty list."""
        with patch("django.conf.settings") as mock_settings:
            del mock_settings.DOLT_DATABASES
            mock_settings.configure_mock(**{"DOLT_DATABASES": AttributeError})
            # Use getattr default behavior
            reset_dolt_databases()
            # We need to properly simulate missing attribute
        reset_dolt_databases()
        with patch("django.conf.settings", spec=[]):
            result = get_dolt_databases()
            assert result == []

    def test_get_dolt_databases_empty_list(self) -> None:
        with patch("django.conf.settings.DOLT_DATABASES", []):
            result = get_dolt_databases()
            assert result == []


class TestProxyModelFactory:
    """Tests for proxy model creation."""

    def test_create_proxy_models_returns_three_models(self) -> None:
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("test_db")
        assert BranchProxy.__name__ == "Branch_test_db"
        assert CommitProxy.__name__ == "Commit_test_db"
        assert RemoteProxy.__name__ == "Remote_test_db"

    def test_create_proxy_models_sets_database_attribute(self) -> None:
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("mydb")
        assert BranchProxy._database == "mydb"
        assert CommitProxy._database == "mydb"
        assert RemoteProxy._database == "mydb"

    def test_create_proxy_models_sets_app_label(self) -> None:
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("mydb")
        assert BranchProxy._meta.app_label == "django_dolt"
        assert CommitProxy._meta.app_label == "django_dolt"
        assert RemoteProxy._meta.app_label == "django_dolt"

    def test_create_proxy_models_caches_result(self) -> None:
        result1 = create_proxy_models("cache_test")
        result2 = create_proxy_models("cache_test")
        assert result1 is result2

    def test_get_proxy_models_returns_none_for_unknown(self) -> None:
        result = get_proxy_models("unknown_db_alias")
        assert result is None

    def test_get_proxy_models_returns_cached_models(self) -> None:
        created = create_proxy_models("cached_test")
        retrieved = get_proxy_models("cached_test")
        assert retrieved is created

    def test_create_proxy_models_handles_special_characters(self) -> None:
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("my-db.test")
        assert BranchProxy.__name__ == "Branch_my_db_test"
        assert BranchProxy._meta.app_label == "django_dolt"


@pytest.fixture()
def multi_dolt_dbs(django_db_blocker: object) -> Generator[list[str], None, None]:
    """Create two fresh test databases, return aliases."""
    with django_db_blocker.unblock():  # type: ignore[union-attr]
        conn = connections["dolt"]
        for db_name in ("test_dolt1", "test_dolt2"):
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
                cursor.execute(f"CREATE DATABASE `{db_name}`")

        for alias in ("dolt1", "dolt2"):
            connections[alias].close()

        yield ["dolt1", "dolt2"]

        for alias in ("dolt1", "dolt2"):
            connections[alias].close()
        for db_name in ("test_dolt1", "test_dolt2"):
            with conn.cursor() as cursor:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")


class TestMultiDatabaseIntegration:
    """Integration tests for multi-database support against real Dolt."""

    def test_independent_commits_across_databases(
        self, multi_dolt_dbs: list[str]
    ) -> None:
        """Each database should have independent commit history."""
        db1, db2 = multi_dolt_dbs

        with connections[db1].cursor() as cursor:
            cursor.execute("CREATE TABLE shared_name (id INT PRIMARY KEY)")
        dolt_add(".", using=db1)
        hash1 = dolt_commit("commit in db1", using=db1)

        with connections[db2].cursor() as cursor:
            cursor.execute("CREATE TABLE other_table (id INT PRIMARY KEY)")
        dolt_add(".", using=db2)
        hash2 = dolt_commit("commit in db2", using=db2)

        assert hash1 is not None
        assert hash2 is not None
        assert hash1 != hash2

        log1 = dolt_log(limit=5, using=db1)
        log2 = dolt_log(limit=5, using=db2)
        messages1 = [r["message"] for r in log1]
        messages2 = [r["message"] for r in log2]
        assert "commit in db1" in messages1
        assert "commit in db1" not in messages2
        assert "commit in db2" in messages2

    def test_branch_operations_per_database(self, multi_dolt_dbs: list[str]) -> None:
        """Branch operations should be independent per database."""
        db1, db2 = multi_dolt_dbs

        branch1 = dolt_current_branch(using=db1)
        branch2 = dolt_current_branch(using=db2)
        assert branch1 == "main"
        assert branch2 == "main"

        branches1 = dolt_branch_list(using=db1)
        branches2 = dolt_branch_list(using=db2)
        assert "main" in branches1
        assert "main" in branches2

    def test_status_per_database(self, multi_dolt_dbs: list[str]) -> None:
        """Status should reflect changes only in the target database."""
        db1, db2 = multi_dolt_dbs

        with connections[db1].cursor() as cursor:
            cursor.execute("CREATE TABLE only_in_db1 (id INT PRIMARY KEY)")

        status1 = dolt_status(exclude_ignored=False, using=db1)
        status2 = dolt_status(exclude_ignored=False, using=db2)

        tables1 = [r["table_name"] for r in status1]
        tables2 = [r["table_name"] for r in status2]
        assert "only_in_db1" in tables1
        assert "only_in_db1" not in tables2
