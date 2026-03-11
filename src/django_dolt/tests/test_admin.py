"""Tests for django_dolt.admin module."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from django_dolt.admin import (
    DoltAdminMixin,
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

    @patch("django_dolt.admin.services.dolt_add_and_commit", return_value="abc12345")
    @patch("django_dolt.admin._get_dolt_db_for_model", return_value="mydb")
    def test_do_dolt_commit_triggers_commit(
        self, mock_get_db: MagicMock, mock_commit: MagicMock
    ) -> None:
        request = self.factory.post("/")
        request.user = self.superuser
        # Need message middleware
        from django.contrib.messages.storage.fallback import FallbackStorage

        request.session = "session"
        request._messages = FallbackStorage(request)

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

        request.session = "session"
        request._messages = FallbackStorage(request)

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

        request.session = "session"
        request._messages = FallbackStorage(request)

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


@pytest.mark.django_db
class TestDoltAdminMixinPullView(TestCase):
    """Test DoltAdminMixin.dolt_pull_view permission checks."""

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.regular_user = User.objects.create_user(
            "pulluser", "pulluser@example.com", "password"
        )

    def test_pull_post_requires_superuser(self) -> None:
        """POST to dolt_pull_view should raise PermissionDenied for non-superuser."""
        from django.contrib.admin import AdminSite

        class TestSite(DoltAdminMixin, AdminSite):
            pass

        site = TestSite()
        request = self.factory.post("/", {"remote": "origin"})
        request.user = self.regular_user

        from django.core.exceptions import PermissionDenied

        with pytest.raises(PermissionDenied):
            site.dolt_pull_view(request)
