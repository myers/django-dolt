"""Tests for django_dolt management commands."""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command


class TestDoltStatusCommand:
    """Tests for the dolt_status management command."""

    @patch("django_dolt.management.commands.dolt_status.services")
    def test_status_no_changes(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_status.return_value = []
        mock_services.get_ignored_tables.return_value = []

        out = StringIO()
        call_command("dolt_status", stdout=out)
        output = out.getvalue()

        assert "Branch: main" in output
        assert "No uncommitted changes" in output

    @patch("django_dolt.management.commands.dolt_status.services")
    def test_status_with_changes(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_status.return_value = [
            {"table_name": "users", "staged": 0, "status": "modified"},
        ]
        mock_services.get_ignored_tables.return_value = []
        mock_services.format_status_rows.return_value = "  modified: users (modified)"

        out = StringIO()
        call_command("dolt_status", stdout=out)
        output = out.getvalue()

        assert "Uncommitted changes" in output
        assert "modified: users" in output

    @patch("django_dolt.management.commands.dolt_status.services")
    def test_status_with_log_flag(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_status.return_value = []
        mock_services.get_ignored_tables.return_value = []
        mock_services.dolt_log.return_value = [
            {
                "commit_hash": "abcdef1234567890",
                "date": "2025-01-01",
                "message": "Initial commit",
            },
        ]

        out = StringIO()
        call_command("dolt_status", "--log", "5", stdout=out)
        output = out.getvalue()

        assert "abcdef12" in output
        assert "Initial commit" in output

    @patch("django_dolt.management.commands.dolt_status.services")
    def test_status_with_database_flag(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "dev"
        mock_services.dolt_status.return_value = []
        mock_services.get_ignored_tables.return_value = []

        out = StringIO()
        call_command("dolt_status", "--database", "mydb", stdout=out)

        mock_services.dolt_current_branch.assert_called_with(using="mydb")
        mock_services.dolt_status.assert_called_with(exclude_ignored=True, using="mydb")


class TestDoltSyncCommand:
    """Tests for the dolt_sync management command."""

    @patch("django_dolt.management.commands.dolt_sync.services")
    def test_sync_stages_and_commits(self, mock_services: MagicMock) -> None:
        mock_services.dolt_status.return_value = [
            {"table_name": "products", "staged": 0, "status": "modified"},
        ]
        mock_services.format_status_rows.return_value = (
            "  modified: products (modified)"
        )
        mock_services.dolt_commit.return_value = "abc12345678"
        mock_services.DoltError = Exception
        mock_services.DoltCommitError = Exception
        mock_services.DoltPushError = Exception

        out = StringIO()
        call_command("dolt_sync", "test commit", "--no-push", stdout=out)

        mock_services.dolt_add.assert_called_with("products", using=None)
        mock_services.dolt_commit.assert_called_once()

    @patch("django_dolt.management.commands.dolt_sync.services")
    def test_sync_no_push_flag(self, mock_services: MagicMock) -> None:
        mock_services.dolt_status.return_value = [
            {"table_name": "t", "staged": 0, "status": "modified"},
        ]
        mock_services.format_status_rows.return_value = "  modified: t (modified)"
        mock_services.dolt_commit.return_value = "abc12345678"
        mock_services.DoltError = Exception
        mock_services.DoltCommitError = Exception

        out = StringIO()
        call_command("dolt_sync", "msg", "--no-push", stdout=out)

        mock_services.dolt_push.assert_not_called()

    @patch("django_dolt.management.commands.dolt_sync.services")
    def test_sync_handles_no_changes(self, mock_services: MagicMock) -> None:
        mock_services.dolt_status.return_value = []
        mock_services.DoltPushError = Exception

        out = StringIO()
        call_command("dolt_sync", "--no-push", stdout=out)
        output = out.getvalue()

        assert "No changes to commit" in output

    @patch("django_dolt.management.commands.dolt_sync.services")
    def test_sync_force_push(self, mock_services: MagicMock) -> None:
        mock_services.dolt_status.return_value = [
            {"table_name": "t", "staged": 0, "status": "modified"},
        ]
        mock_services.format_status_rows.return_value = "  modified: t (modified)"
        mock_services.dolt_commit.return_value = "abc12345678"
        mock_services.dolt_push.return_value = "Pushed"
        mock_services.DoltError = Exception
        mock_services.DoltCommitError = Exception
        mock_services.DoltPushError = Exception

        out = StringIO()
        call_command("dolt_sync", "msg", "--force", stdout=out)

        mock_services.dolt_push.assert_called_with(force=True, using=None)


class TestDoltPullCommand:
    """Tests for the dolt_pull management command."""

    @patch("django_dolt.management.commands.dolt_pull.services")
    def test_pull_default(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_pull.return_value = "Fast-forward pull successful"
        mock_services.dolt_log.return_value = []
        mock_services.DoltPullError = Exception

        out = StringIO()
        call_command("dolt_pull", stdout=out)
        output = out.getvalue()

        assert "Fast-forward pull successful" in output
        mock_services.dolt_pull.assert_called_once()

    @patch("django_dolt.management.commands.dolt_pull.services")
    def test_pull_fetch_only(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_fetch.return_value = "Fetched from origin"
        mock_services.dolt_log.return_value = []
        mock_services.DoltError = Exception

        out = StringIO()
        call_command("dolt_pull", "--fetch-only", stdout=out)
        output = out.getvalue()

        assert "Fetched from origin" in output
        mock_services.dolt_pull.assert_not_called()

    @patch("django_dolt.management.commands.dolt_pull.services")
    def test_pull_with_user_flag(self, mock_services: MagicMock) -> None:
        mock_services.dolt_current_branch.return_value = "main"
        mock_services.dolt_pull.return_value = "Already up to date"
        mock_services.dolt_log.return_value = []
        mock_services.DoltPullError = Exception

        out = StringIO()
        call_command("dolt_pull", "--user", "myuser", stdout=out)

        mock_services.dolt_pull.assert_called_once()
        call_kwargs = mock_services.dolt_pull.call_args[1]
        assert call_kwargs.get("user") == "myuser"
