"""Tests for django_dolt.services module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from django_dolt import services


class TestDoltExceptions:
    """Test exception hierarchy."""

    def test_dolt_error_is_base(self) -> None:
        assert issubclass(services.DoltCommitError, services.DoltError)
        assert issubclass(services.DoltPushError, services.DoltError)
        assert issubclass(services.DoltPullError, services.DoltError)

    def test_exceptions_have_messages(self) -> None:
        exc = services.DoltError("test message")
        assert str(exc) == "test message"


class TestDoltAdd:
    """Test dolt_add function."""

    @patch("django_dolt.services.connection")
    def test_add_single_table(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        services.dolt_add("my_table")

        mock_cursor.execute.assert_called_once_with(
            "CALL DOLT_ADD(%s)", ["my_table"]
        )

    @patch("django_dolt.services.connection")
    def test_add_all_tables(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        services.dolt_add()

        mock_cursor.execute.assert_called_once_with("CALL DOLT_ADD(%s)", ["."])

    @patch("django_dolt.services.connection")
    def test_add_raises_on_error(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("table not found")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        with pytest.raises(services.DoltError, match="Failed to stage"):
            services.dolt_add("nonexistent")


class TestDoltCommit:
    """Test dolt_commit function."""

    @patch("django_dolt.services.connection")
    def test_commit_returns_hash(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("abc123def456",)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_commit("test message")

        assert result == "abc123def456"
        mock_cursor.execute.assert_called_once()

    @patch("django_dolt.services.connection")
    def test_commit_with_custom_author(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("abc123",)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        services.dolt_commit("msg", author="Test <test@example.com>")

        call_args = mock_cursor.execute.call_args
        assert "Test <test@example.com>" in call_args[0][1]

    @patch("django_dolt.services.connection")
    def test_commit_nothing_to_commit(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("nothing to commit")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_commit("test")

        assert result is None


class TestDoltStatus:
    """Test dolt_status function."""

    @patch("django_dolt.services.connection")
    def test_status_returns_list_of_dicts(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.description = [("table_name",), ("staged",), ("status",)]
        mock_cursor.fetchall.return_value = [
            ("users", 0, "modified"),
            ("posts", 1, "new table"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_status(exclude_ignored=False)

        assert len(result) == 2
        assert result[0]["table_name"] == "users"
        assert result[1]["staged"] == 1


class TestDoltLog:
    """Test dolt_log function."""

    @patch("django_dolt.services.connection")
    def test_log_returns_commits(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("commit_hash",),
            ("committer",),
            ("email",),
            ("date",),
            ("message",),
        ]
        mock_cursor.fetchall.return_value = [
            ("abc123", "Test", "test@example.com", "2024-01-01", "Initial commit"),
        ]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_log(limit=10)

        assert len(result) == 1
        assert result[0]["commit_hash"] == "abc123"
        assert result[0]["message"] == "Initial commit"


class TestDoltBranch:
    """Test branch-related functions."""

    @patch("django_dolt.services.connection")
    def test_current_branch(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("main",)
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_current_branch()

        assert result == "main"

    @patch("django_dolt.services.connection")
    def test_branch_list(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("main",), ("feature",)]
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_branch_list()

        assert result == ["main", "feature"]


class TestDoltPush:
    """Test dolt_push function."""

    @patch("django_dolt.services.connection")
    def test_push_success(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_push(remote="origin", branch="main")

        assert "Pushed main to origin" in result

    @patch("django_dolt.services.connection")
    def test_push_with_force(self, mock_connection: MagicMock) -> None:
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        services.dolt_push(force=True)

        call_args = mock_cursor.execute.call_args[0][1]
        assert "--force" in call_args


class TestDoltPull:
    """Test dolt_pull function."""

    @patch("django_dolt.services.dolt_current_branch")
    @patch("django_dolt.services.connection")
    def test_pull_success(
        self, mock_connection: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_branch.return_value = "main"
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1, 0)  # fast_forward, no conflicts
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_pull()

        assert "Fast-forward" in result

    @patch("django_dolt.services.dolt_current_branch")
    @patch("django_dolt.services.connection")
    def test_pull_with_conflicts(
        self, mock_connection: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_branch.return_value = "main"
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0, 3)  # not fast_forward, 3 conflicts
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = services.dolt_pull()

        assert "conflicts" in result
