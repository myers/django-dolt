"""Tests for django_dolt.services module against a real Dolt database."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from django.db import connections

from django_dolt import services


# All tests in this module need database access
class TestDoltExceptions:
    """Test exception hierarchy."""

    def test_dolt_error_is_base(self) -> None:
        assert issubclass(services.DoltCommitError, services.DoltError)
        assert issubclass(services.DoltPushError, services.DoltError)
        assert issubclass(services.DoltPullError, services.DoltError)

    def test_exceptions_have_messages(self) -> None:
        exc = services.DoltError("test message")
        assert str(exc) == "test message"


@pytest.fixture()
def dolt_db(django_db_blocker: object) -> Generator[str, None, None]:
    """Create a fresh test database for each test, return the alias."""
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        conn = connections["dolt"]
        db_name = "test_services"
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            cursor.execute(f"CREATE DATABASE `{db_name}`")

        # Point dolt1 alias at our test db
        old_name = connections.databases["dolt1"]["NAME"]
        connections.databases["dolt1"]["NAME"] = db_name
        connections["dolt1"].close()

        yield "dolt1"

        connections.databases["dolt1"]["NAME"] = old_name
        connections["dolt1"].close()
        with conn.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")


class TestDoltAdd:
    """Test dolt_add function against real Dolt."""

    def test_add_all_tables_no_changes(self, dolt_db: str) -> None:
        """Adding with no changes should succeed without error."""
        services.dolt_add(".", using=dolt_db)

    def test_add_nonexistent_table(self, dolt_db: str) -> None:
        """Adding a nonexistent table should raise DoltError."""
        with pytest.raises(services.DoltError, match="Failed to stage"):
            services.dolt_add("nonexistent_table_xyz", using=dolt_db)


class TestDoltCommit:
    """Test dolt_commit function against real Dolt."""

    def test_commit_with_changes(self, dolt_db: str) -> None:
        """Commit should return a hash when there are staged changes."""
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE test_commit_tbl (id INT PRIMARY KEY, val VARCHAR(50))"
            )
            cursor.execute("INSERT INTO test_commit_tbl VALUES (1, 'hello')")

        services.dolt_add(".", using=dolt_db)
        result = services.dolt_commit("test commit", using=dolt_db)

        assert result is not None
        assert len(result) > 8

    def test_commit_nothing_to_commit(self, dolt_db: str) -> None:
        """Commit with no changes should return None."""
        result = services.dolt_commit("empty commit", using=dolt_db)
        assert result is None

    def test_commit_allow_empty(self, dolt_db: str) -> None:
        """Commit with allow_empty should succeed even with no changes."""
        result = services.dolt_commit("empty commit", allow_empty=True, using=dolt_db)
        assert result is not None

    def test_commit_with_custom_author(self, dolt_db: str) -> None:
        """Commit should accept a custom author."""
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE test_author_tbl (id INT PRIMARY KEY)")

        services.dolt_add(".", using=dolt_db)
        result = services.dolt_commit(
            "author test",
            author="Test User <test@example.com>",
            using=dolt_db,
        )
        assert result is not None


class TestDoltStatus:
    """Test dolt_status function against real Dolt."""

    def test_status_empty(self, dolt_db: str) -> None:
        """Status with no changes should return empty list."""
        result = services.dolt_status(exclude_ignored=False, using=dolt_db)
        assert result == []

    def test_status_with_changes(self, dolt_db: str) -> None:
        """Status should show modified tables."""
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE test_status_tbl (id INT PRIMARY KEY, val VARCHAR(50))"
            )

        result = services.dolt_status(exclude_ignored=False, using=dolt_db)
        assert len(result) >= 1
        table_names = [r["table_name"] for r in result]
        assert "test_status_tbl" in table_names


class TestDoltLog:
    """Test dolt_log function against real Dolt."""

    def test_log_returns_commits(self, dolt_db: str) -> None:
        """Log should return at least the initial commit."""
        result = services.dolt_log(limit=10, using=dolt_db)
        assert len(result) >= 1
        assert "commit_hash" in result[0]
        assert "message" in result[0]

    def test_log_shows_our_commit(self, dolt_db: str) -> None:
        """Log should include commits we make."""
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE test_log_tbl (id INT PRIMARY KEY)")
        services.dolt_add(".", using=dolt_db)
        services.dolt_commit("log test commit", using=dolt_db)

        result = services.dolt_log(limit=10, using=dolt_db)
        messages = [r["message"] for r in result]
        assert "log test commit" in messages


class TestDoltBranch:
    """Test branch-related functions against real Dolt."""

    def test_current_branch(self, dolt_db: str) -> None:
        result = services.dolt_current_branch(using=dolt_db)
        assert result == "main"

    def test_branch_list(self, dolt_db: str) -> None:
        result = services.dolt_branch_list(using=dolt_db)
        assert "main" in result


class TestDoltAddAndCommit:
    """Test dolt_add_and_commit convenience function."""

    def test_add_and_commit(self, dolt_db: str) -> None:
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE test_addcommit (id INT PRIMARY KEY)")

        result = services.dolt_add_and_commit("add-and-commit test", using=dolt_db)
        assert result is not None

    def test_add_and_commit_no_changes(self, dolt_db: str) -> None:
        result = services.dolt_add_and_commit("no changes", using=dolt_db)
        assert result is None

    def test_add_and_commit_stages_new_tables(self, dolt_db: str) -> None:
        """Stage-all should pick up newly created tables."""
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE test_new_tbl (id INT PRIMARY KEY)")
            cursor.execute("INSERT INTO test_new_tbl VALUES (1)")

        result = services.dolt_add_and_commit("new table test", using=dolt_db)
        assert result is not None


class TestDoltDiff:
    """Test dolt_diff function against real Dolt."""

    def test_diff_no_changes(self, dolt_db: str) -> None:
        result = services.dolt_diff(using=dolt_db)
        assert result == []

    def test_diff_with_changes(self, dolt_db: str) -> None:
        conn = connections[dolt_db]
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE test_diff_tbl (id INT PRIMARY KEY)")
        services.dolt_add(".", using=dolt_db)
        services.dolt_commit("before diff", using=dolt_db)

        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO test_diff_tbl VALUES (1)")
        services.dolt_add(".", using=dolt_db)
        services.dolt_commit("after diff", using=dolt_db)

        log = services.dolt_log(limit=2, using=dolt_db)
        result = services.dolt_diff(
            from_ref=log[1]["commit_hash"],
            to_ref=log[0]["commit_hash"],
            table="test_diff_tbl",
            using=dolt_db,
        )
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Mock-based tests — patch models functions / managers
# ---------------------------------------------------------------------------


class TestDoltPushMocked:
    """Test dolt_push with mocked models.dolt_push."""

    @patch("django_dolt.models.dolt_push")
    def test_push_success(self, mock_push: MagicMock) -> None:
        result = services.dolt_push(remote="origin", branch="main")
        assert "Pushed" in result
        mock_push.assert_called_once()

    @patch("django_dolt.models.dolt_push")
    def test_push_failure_raises_push_error(self, mock_push: MagicMock) -> None:
        mock_push.side_effect = Exception("push denied")
        with pytest.raises(services.DoltPushError, match="push denied"):
            services.dolt_push()

    @patch("django_dolt.models.dolt_push")
    def test_push_with_force(self, mock_push: MagicMock) -> None:
        services.dolt_push(force=True)
        args = mock_push.call_args[0][0]
        assert "--force" in args


class TestDoltFetchMocked:
    """Test dolt_fetch with mocked models.dolt_fetch."""

    @patch("django_dolt.models.dolt_fetch")
    def test_fetch_success(self, mock_fetch: MagicMock) -> None:
        result = services.dolt_fetch(remote="origin")
        assert "Fetched from origin" in result

    @patch("django_dolt.models.dolt_fetch")
    def test_fetch_failure_raises_dolt_error(self, mock_fetch: MagicMock) -> None:
        mock_fetch.side_effect = Exception("network error")
        with pytest.raises(services.DoltError, match="network error"):
            services.dolt_fetch()


class TestDoltAddRemoteMocked:
    """Test dolt_add_remote with mocked models.dolt_add_remote."""

    @patch("django_dolt.models.dolt_add_remote")
    def test_add_remote_success(self, mock_add_remote: MagicMock) -> None:
        services.dolt_add_remote("origin", "https://example.com/repo")
        mock_add_remote.assert_called_once_with(
            "origin", "https://example.com/repo", using=None
        )

    @patch("django_dolt.models.dolt_add_remote")
    def test_add_remote_failure(self, mock_add_remote: MagicMock) -> None:
        mock_add_remote.side_effect = Exception("already exists")
        with pytest.raises(services.DoltError, match="already exists"):
            services.dolt_add_remote("origin", "https://example.com")


class TestDoltRemotesMocked:
    """Test dolt_remotes via ORM manager mock."""

    @patch("django_dolt.models.RemoteManager.all_remotes")
    def test_remotes_returns_list(self, mock_all_remotes: MagicMock) -> None:
        mock_all_remotes.return_value = [
            {"name": "origin", "url": "https://example.com"}
        ]

        result = services.dolt_remotes()
        assert len(result) == 1
        assert result[0]["name"] == "origin"
        assert result[0]["url"] == "https://example.com"


class TestGetIgnoredTablesMocked:
    """Test get_ignored_tables via ORM manager mock."""

    @patch("django_dolt.models.IgnoreManager.patterns")
    def test_ignored_tables_returns_patterns(
        self, mock_patterns: MagicMock
    ) -> None:
        mock_patterns.return_value = ["django_%", "auth_%"]

        result = services.get_ignored_tables()
        assert result == ["django_%", "auth_%"]


class TestDoltStatusErrorHandling:
    """Test dolt_status error handling."""

    @patch("django_dolt.models.StatusManager.current")
    def test_status_wraps_exception_in_dolt_error(
        self, mock_current: MagicMock
    ) -> None:
        mock_current.side_effect = Exception("connection lost")

        with pytest.raises(services.DoltError, match="connection lost"):
            services.dolt_status(exclude_ignored=False)

    @patch("django_dolt.models.Status.objects.current")
    def test_status_exclude_ignored_error_propagates(
        self, mock_current: MagicMock
    ) -> None:
        """When dolt_ignore query fails, error propagates."""
        mock_current.side_effect = Exception(
            "table dolt_ignore doesn't exist"
        )

        with pytest.raises(
            services.DoltError, match="dolt_ignore"
        ):
            services.dolt_status(exclude_ignored=True)


class TestDoltPullMocked:
    """Test dolt_pull with mocked models.dolt_pull."""

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="main")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_fast_forward(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.return_value = (1, 0)
        result = services.dolt_pull(remote="origin", branch="main")
        assert "Fast-forward" in result

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="main")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_with_conflicts(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.return_value = (1, 3)
        result = services.dolt_pull(remote="origin", branch="main")
        assert "conflicts" in result

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="main")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_already_up_to_date(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.return_value = (0, 0)
        result = services.dolt_pull(remote="origin", branch="main")
        assert "up to date" in result

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="main")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_none_result(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.return_value = None
        result = services.dolt_pull(remote="origin", branch="main")
        assert "Pull completed" in result

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="main")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_failure_raises_pull_error(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.side_effect = Exception("connection refused")
        with pytest.raises(services.DoltPullError, match="connection refused"):
            services.dolt_pull()

    @patch("django_dolt.models.Branch.objects.active_branch", return_value="dev")
    @patch("django_dolt.models.dolt_pull")
    def test_pull_resolves_branch_from_active(
        self, mock_pull: MagicMock, mock_branch: MagicMock
    ) -> None:
        mock_pull.return_value = (1, 0)
        services.dolt_pull(branch=None)
        args = mock_pull.call_args[0][0]
        assert "dev" in args


class TestFormatStatusRows:
    """Test format_status_rows utility function."""

    def test_empty_rows(self) -> None:
        assert services.format_status_rows([]) == "No changes"

    def test_single_modified_row(self) -> None:
        rows = [{"table_name": "users", "staged": 0, "status": "modified"}]
        result = services.format_status_rows(rows)
        assert "unstaged: users (modified)" in result

    def test_staged_row(self) -> None:
        rows = [{"table_name": "orders", "staged": 1, "status": "new table"}]
        result = services.format_status_rows(rows)
        assert "staged: orders (new table)" in result

    def test_multiple_rows(self) -> None:
        rows = [
            {"table_name": "a", "staged": 0, "status": "modified"},
            {"table_name": "b", "staged": 1, "status": "new table"},
        ]
        result = services.format_status_rows(rows)
        lines = result.strip().split("\n")
        assert len(lines) == 2
