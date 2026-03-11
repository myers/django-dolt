"""Tests for django_dolt.admin module."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from django_dolt.admin import (
    DoltCommitMixin,
    ReadOnlyModelAdmin,
    _make_diff_view,
    _make_status_view,
)


@pytest.mark.django_db
class TestReadOnlyModelAdmin(TestCase):
    """Test ReadOnlyModelAdmin permission methods."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.admin = ReadOnlyModelAdmin(User, MagicMock())

    def test_has_add_permission_returns_false(self) -> None:
        request = self.factory.get("/")
        assert self.admin.has_add_permission(request) is False

    def test_has_change_permission_returns_false(self) -> None:
        request = self.factory.get("/")
        assert self.admin.has_change_permission(request) is False

    def test_has_delete_permission_returns_false(self) -> None:
        request = self.factory.get("/")
        assert self.admin.has_delete_permission(request) is False


@pytest.mark.django_db
class TestDoltCommitMixin(TestCase):
    """Test DoltCommitMixin._do_dolt_commit."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )

    @patch("django_dolt.admin._get_dolt_db_for_model", return_value=None)
    def test_do_dolt_commit_no_dolt_db_is_noop(self, mock_get_db: MagicMock) -> None:
        """When the model isn't routed to a Dolt DB, commit is a no-op."""
        request = self.factory.post("/")
        request.user = self.superuser

        mixin = DoltCommitMixin()
        mixin._do_dolt_commit(request, MagicMock())  # should not raise

    @patch("django_dolt.admin.services.dolt_add_and_commit", side_effect=Exception("db error"))
    @patch("django_dolt.admin._get_dolt_db_for_model", return_value="mydb")
    def test_do_dolt_commit_handles_exception(
        self, mock_get_db: MagicMock, mock_commit: MagicMock
    ) -> None:
        """When dolt_add_and_commit raises, the error is caught and a message is added."""
        request = self.factory.post("/")
        request.user = self.superuser
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        mixin = DoltCommitMixin()
        obj = MagicMock()
        obj.__class__.__name__ = "TestModel"
        mixin._do_dolt_commit(request, obj)  # should not raise

        stored_messages = list(request._messages)  # type: ignore[attr-defined]
        assert len(stored_messages) == 1
        assert "Commit failed" in str(stored_messages[0])

    @patch("django_dolt.admin.services.dolt_add_and_commit", return_value="abc12345")
    @patch("django_dolt.admin._get_dolt_db_for_model", return_value="mydb")
    def test_do_dolt_commit_triggers_commit(
        self, mock_get_db: MagicMock, mock_commit: MagicMock
    ) -> None:
        request = self.factory.post("/")
        request.user = self.superuser
        # Need message middleware
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        mixin = DoltCommitMixin()
        obj = MagicMock()
        obj.__class__.__name__ = "TestModel"
        mixin._do_dolt_commit(request, obj)

        mock_commit.assert_called_once()


@pytest.mark.django_db
class TestMakeStatusView(TestCase):
    """Test _make_status_view."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            "admin", "admin@example.com", "password"
        )
        self.regular_user = User.objects.create_user(
            "user", "user@example.com", "password"
        )

    @patch("django_dolt.admin.services.dolt_log", return_value=[])
    @patch("django_dolt.admin.services.dolt_current_branch", return_value="main")
    @patch("django_dolt.admin.services.dolt_status", return_value=[])
    def test_get_renders_template(
        self, mock_status: MagicMock, mock_branch: MagicMock, mock_log: MagicMock
    ) -> None:
        view = _make_status_view("testdb")
        request = self.factory.get("/")
        request.user = self.superuser

        with patch("django_dolt.admin.admin.site.each_context", return_value={}):
            response = view(request)
        assert response.status_code == 200
        assert response.template_name == "admin/django_dolt/status.html"

    @patch("django_dolt.admin.reverse", return_value="/admin/dolt/status/testdb/")
    @patch("django_dolt.admin.services.dolt_commit", return_value="abcdef12")
    @patch("django_dolt.admin.services.dolt_add")
    def test_post_commits_as_superuser(
        self, mock_add: MagicMock, mock_commit: MagicMock, mock_reverse: MagicMock
    ) -> None:
        view = _make_status_view("testdb")
        request = self.factory.post("/", {"message": "test commit"})
        request.user = self.superuser
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        response = view(request)
        assert response.status_code == 302
        mock_commit.assert_called_once()

    def test_post_rejected_for_non_superuser(self) -> None:
        view = _make_status_view("testdb")
        request = self.factory.post("/", {"message": "test commit"})
        request.user = self.regular_user

        from django.core.exceptions import PermissionDenied

        with pytest.raises(PermissionDenied):
            view(request)

    @patch("django_dolt.admin.reverse", return_value="/admin/dolt/status/testdb/")
    @patch("django_dolt.admin.services.dolt_commit", return_value=None)
    @patch("django_dolt.admin.services.dolt_add")
    def test_post_handles_none_result(
        self, mock_add: MagicMock, mock_commit: MagicMock, mock_reverse: MagicMock
    ) -> None:
        """When dolt_commit returns None, should show info message not crash."""
        view = _make_status_view("testdb")
        request = self.factory.post("/", {"message": "test commit"})
        request.user = self.superuser
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        response = view(request)
        assert response.status_code == 302


@pytest.mark.django_db
class TestMakeDiffView(TestCase):
    """Test _make_diff_view."""

    @patch("django_dolt.admin.services.dolt_diff", return_value=[])
    @patch("django_dolt.admin.reverse")
    def test_renders_diff_template(
        self, mock_reverse: MagicMock, mock_diff: MagicMock
    ) -> None:
        mock_reverse.return_value = "/admin/dolt/status/testdb/"
        view = _make_diff_view("testdb")
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(
            "admin2", "admin2@example.com", "password"
        )

        with patch("django_dolt.admin.admin.site.each_context", return_value={}):
            response = view(request, "my_table")
        assert response.status_code == 200
        assert response.template_name == "admin/django_dolt/diff.html"

    @patch("django_dolt.admin.services.dolt_diff")
    @patch("django_dolt.admin.reverse")
    def test_renders_diff_with_data(
        self, mock_reverse: MagicMock, mock_diff: MagicMock
    ) -> None:
        mock_reverse.return_value = "/admin/dolt/status/testdb/"
        mock_diff.return_value = [
            {
                "diff_type": "modified",
                "from_id": 1,
                "to_id": 1,
                "from_name": "old",
                "to_name": "new",
                "from_commit": "aaa",
                "to_commit": "bbb",
                "from_commit_date": "2025-01-01",
                "to_commit_date": "2025-01-02",
            }
        ]
        view = _make_diff_view("testdb")
        request = RequestFactory().get("/")
        request.user = User.objects.create_superuser(
            "admin_diff", "admin_diff@example.com", "password"
        )

        with patch("django_dolt.admin.admin.site.each_context", return_value={}):
            response = view(request, "my_table")
        assert response.status_code == 200
        assert "columns" in response.context_data
        assert "diff_rows" in response.context_data
        assert len(response.context_data["columns"]) > 0
        assert len(response.context_data["diff_rows"]) == 1
        cells = response.context_data["diff_rows"][0]["cells"]
        assert any(c["changed"] for c in cells)

    @patch("django_dolt.admin.reverse", return_value="/admin/dolt/status/testdb/")
    def test_non_get_redirects_to_status(self, mock_reverse: MagicMock) -> None:
        """Non-GET requests should redirect to status page."""
        view = _make_diff_view("testdb")
        request = RequestFactory().post("/")
        request.user = User.objects.create_superuser(
            "admin3", "admin3@example.com", "password"
        )

        response = view(request, "my_table")
        assert response.status_code == 302


@pytest.mark.django_db
class TestDoltCommitMixinResponseAdd(TestCase):
    """Test DoltCommitMixin.response_add with _save_and_commit."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            "commitadmin", "commitadmin@example.com", "password"
        )

    @patch("django_dolt.admin.services.dolt_add_and_commit", return_value="abc12345")
    @patch("django_dolt.admin._get_dolt_db_for_model", return_value="mydb")
    def test_response_add_with_save_and_commit(
        self, mock_get_db: MagicMock, mock_commit: MagicMock
    ) -> None:
        """response_add triggers commit with _save_and_commit."""
        from django.contrib import admin
        from django.contrib.messages.storage.fallback import FallbackStorage

        class TestModel:
            pk = 1

            def __str__(self) -> str:
                return "test"

        class TestAdmin(DoltCommitMixin, admin.ModelAdmin):  # type: ignore[misc, type-arg]
            pass

        model_admin = TestAdmin(User, admin.site)
        request = self.factory.post("/", {"_save_and_commit": "1"})
        request.user = self.superuser
        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        obj = TestModel()
        mock_resp = MagicMock(status_code=302)
        with patch.object(
            admin.ModelAdmin, "response_add", return_value=mock_resp
        ):
            model_admin.response_add(request, obj)

        mock_commit.assert_called_once()

    @patch("django_dolt.admin.services.dolt_add_and_commit", return_value="abc12345")
    @patch("django_dolt.admin._get_dolt_db_for_model", return_value="mydb")
    def test_response_change_with_save_and_commit(
        self, mock_get_db: MagicMock, mock_commit: MagicMock
    ) -> None:
        """response_change triggers commit with _save_and_commit."""
        from django.contrib import admin
        from django.contrib.messages.storage.fallback import FallbackStorage

        class TestModel:
            pk = 1

            def __str__(self) -> str:
                return "test"

        class TestAdmin(DoltCommitMixin, admin.ModelAdmin):  # type: ignore[misc, type-arg]
            pass

        model_admin = TestAdmin(User, admin.site)
        request = self.factory.post("/", {"_save_and_commit": "1"})
        request.user = self.superuser
        request.session = "session"  # type: ignore[assignment]
        request._messages = FallbackStorage(request)  # type: ignore[attr-defined]

        obj = TestModel()
        mock_resp = MagicMock(status_code=302)
        with patch.object(
            admin.ModelAdmin, "response_change", return_value=mock_resp
        ):
            model_admin.response_change(request, obj)

        mock_commit.assert_called_once()
