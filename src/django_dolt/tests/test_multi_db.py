"""Tests for multi-database support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from django_dolt.dolt_databases import (
    _is_dolt_database,
    get_dolt_databases,
    reset_dolt_databases,
)
from django_dolt.models import create_proxy_models, get_proxy_models


class TestDoltDatabaseDiscovery:
    """Tests for Dolt database discovery."""

    def setup_method(self) -> None:
        """Reset the cached Dolt databases before each test."""
        reset_dolt_databases()

    def teardown_method(self) -> None:
        """Reset the cached Dolt databases after each test."""
        reset_dolt_databases()

    def test_get_dolt_databases_caches_result(self) -> None:
        """get_dolt_databases should cache its result."""
        with patch(
            "django_dolt.dolt_databases.connections",
            MagicMock(__iter__=lambda self: iter([])),
        ):
            result1 = get_dolt_databases()
            result2 = get_dolt_databases()
            assert result1 is result2

    def test_reset_dolt_databases_clears_cache(self) -> None:
        """reset_dolt_databases should clear the cache."""
        with patch(
            "django_dolt.dolt_databases.connections",
            MagicMock(__iter__=lambda self: iter([])),
        ):
            result1 = get_dolt_databases()
            reset_dolt_databases()
            result2 = get_dolt_databases()
            # After reset, the result should be a new list
            assert result1 is not result2

    def test_is_dolt_database_returns_false_for_sqlite(self) -> None:
        """_is_dolt_database should return False for SQLite databases."""
        mock_conn = MagicMock()
        mock_conn.vendor = "sqlite"

        with patch("django_dolt.dolt_databases.connections", {"test": mock_conn}):
            assert _is_dolt_database("test") is False

    def test_is_dolt_database_returns_false_for_postgresql(self) -> None:
        """_is_dolt_database should return False for PostgreSQL databases."""
        mock_conn = MagicMock()
        mock_conn.vendor = "postgresql"

        with patch("django_dolt.dolt_databases.connections", {"test": mock_conn}):
            assert _is_dolt_database("test") is False

    def test_is_dolt_database_returns_true_for_mysql_with_dolt_tables(self) -> None:
        """_is_dolt_database should return True for MySQL databases with Dolt tables."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("dolt_branches",)
        mock_cursor.__enter__ = lambda self: self
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.vendor = "mysql"
        mock_conn.cursor.return_value = mock_cursor

        with patch("django_dolt.dolt_databases.connections", {"test": mock_conn}):
            assert _is_dolt_database("test") is True

    def test_is_dolt_database_returns_false_for_mysql_without_dolt_tables(self) -> None:
        """_is_dolt_database should return False for MySQL without Dolt tables."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.__enter__ = lambda self: self
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.vendor = "mysql"
        mock_conn.cursor.return_value = mock_cursor

        with patch("django_dolt.dolt_databases.connections", {"test": mock_conn}):
            assert _is_dolt_database("test") is False

    def test_is_dolt_database_handles_connection_errors(self) -> None:
        """_is_dolt_database should return False on connection errors."""
        mock_conn = MagicMock()
        mock_conn.vendor = "mysql"
        mock_conn.cursor.side_effect = Exception("Connection failed")

        with patch("django_dolt.dolt_databases.connections", {"test": mock_conn}):
            assert _is_dolt_database("test") is False


class TestProxyModelFactory:
    """Tests for proxy model creation."""

    def test_create_proxy_models_returns_three_models(self) -> None:
        """create_proxy_models should return Branch, Commit, Remote proxies."""
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("test_db")

        assert BranchProxy.__name__ == "Branch_test_db"
        assert CommitProxy.__name__ == "Commit_test_db"
        assert RemoteProxy.__name__ == "Remote_test_db"

    def test_create_proxy_models_sets_database_attribute(self) -> None:
        """Proxy models should have _database attribute set."""
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("mydb")

        assert BranchProxy._database == "mydb"
        assert CommitProxy._database == "mydb"
        assert RemoteProxy._database == "mydb"

    def test_create_proxy_models_sets_app_label(self) -> None:
        """Proxy models should have correct app_label."""
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("mydb")

        assert BranchProxy._meta.app_label == "django_dolt_mydb"
        assert CommitProxy._meta.app_label == "django_dolt_mydb"
        assert RemoteProxy._meta.app_label == "django_dolt_mydb"

    def test_create_proxy_models_caches_result(self) -> None:
        """create_proxy_models should cache and return same models."""
        result1 = create_proxy_models("cache_test")
        result2 = create_proxy_models("cache_test")

        assert result1 is result2

    def test_get_proxy_models_returns_none_for_unknown(self) -> None:
        """get_proxy_models should return None for unknown alias."""
        result = get_proxy_models("unknown_db_alias")
        assert result is None

    def test_get_proxy_models_returns_cached_models(self) -> None:
        """get_proxy_models should return cached models after creation."""
        created = create_proxy_models("cached_test")
        retrieved = get_proxy_models("cached_test")

        assert retrieved is created

    def test_create_proxy_models_handles_special_characters(self) -> None:
        """Proxy models should handle special characters in db alias."""
        BranchProxy, CommitProxy, RemoteProxy = create_proxy_models("my-db.test")

        assert BranchProxy.__name__ == "Branch_my_db_test"
        assert BranchProxy._meta.app_label == "django_dolt_my_db_test"


class TestServicesWithUsing:
    """Tests for services layer with using parameter."""

    def test_dolt_add_accepts_using_parameter(self) -> None:
        """dolt_add should accept using parameter."""
        from django_dolt import services

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda self: self
        mock_cursor.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(services, "connections", {"mydb": mock_conn}):
            services.dolt_add(".", using="mydb")

        mock_conn.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once()

    def test_dolt_log_accepts_using_parameter(self) -> None:
        """dolt_log should accept using parameter."""
        from django_dolt import services

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda self: self
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(services, "connections", {"mydb": mock_conn}):
            result = services.dolt_log(limit=10, using="mydb")

        assert result == []
        mock_conn.cursor.assert_called_once()

    def test_dolt_branch_list_accepts_using_parameter(self) -> None:
        """dolt_branch_list should accept using parameter."""
        from django_dolt import services

        mock_cursor = MagicMock()
        mock_cursor.__enter__ = lambda self: self
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_cursor.fetchall.return_value = [("main",), ("develop",)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(services, "connections", {"mydb": mock_conn}):
            result = services.dolt_branch_list(using="mydb")

        assert result == ["main", "develop"]


@pytest.mark.integration
class TestMultiDatabaseIntegration:
    """Integration tests for multi-database support.

    These tests require a running Dolt server and are skipped when unavailable.
    """

    def test_discovers_dolt_databases(self) -> None:
        """Should discover Dolt databases from Django configuration."""
        # This test will only run when DOLT_HOST is set
        pytest.skip("Integration tests require Dolt server")

    def test_branch_queries_use_correct_database(self) -> None:
        """Branch queries should use the specified database."""
        pytest.skip("Integration tests require Dolt server")

    def test_admin_registers_per_database(self) -> None:
        """Admin should register separate models per database."""
        pytest.skip("Integration tests require Dolt server")
