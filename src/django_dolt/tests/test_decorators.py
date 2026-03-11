"""Tests for django_dolt.decorators module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from django_dolt.decorators import dolt_autocommit, get_author_from_request


@pytest.fixture()
def rf() -> RequestFactory:
    return RequestFactory()


@pytest.fixture()
def auth_request(rf: RequestFactory) -> HttpRequest:
    """Request with an authenticated user."""
    request = rf.get("/")
    user = MagicMock()
    user.is_authenticated = True
    user.username = "testuser"
    user.get_full_name.return_value = "Test User"
    user.email = "test@example.com"
    request.user = user
    return request


@pytest.fixture()
def anon_request(rf: RequestFactory) -> HttpRequest:
    """Request with an anonymous user."""
    request = rf.get("/")
    user = MagicMock()
    user.is_authenticated = False
    request.user = user
    return request


class TestGetAuthorFromRequest:
    def test_authenticated_user(self, auth_request: HttpRequest) -> None:
        assert get_author_from_request(auth_request) == "Test User <test@example.com>"

    def test_anonymous_user(self, anon_request: HttpRequest) -> None:
        assert get_author_from_request(anon_request) == "Django <django@localhost>"

    def test_user_without_full_name(self, rf: RequestFactory) -> None:
        request = rf.get("/")
        user = MagicMock()
        user.is_authenticated = True
        user.username = "jdoe"
        user.get_full_name.return_value = ""
        user.email = "jdoe@example.com"
        request.user = user
        assert get_author_from_request(request) == "jdoe <jdoe@example.com>"

    def test_no_user_attribute(self, rf: RequestFactory) -> None:
        request = rf.get("/")
        if hasattr(request, "user"):
            del request.user
        assert get_author_from_request(request) == "Django <django@localhost>"


def _ok_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def _error_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("error", status=500)


def _redirect_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse(status=302)


@pytest.mark.django_db()
class TestDoltAutocommit:
    """Test the dolt_autocommit decorator using mocks."""

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    @patch("django_dolt.decorators.get_dolt_databases")
    def test_commits_when_changes_exist(
        self, mock_dbs: MagicMock, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_dbs.return_value = ["inventory"]
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]
        mock_commit.return_value = "abc123"

        wrapped = dolt_autocommit(_ok_view)
        response = wrapped(auth_request)

        assert response.status_code == 200
        mock_commit.assert_called_once_with(
            message="Auto-commit",
            author="Test User <test@example.com>",
            using="inventory",
        )

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    @patch("django_dolt.decorators.get_dolt_databases")
    def test_skips_when_no_changes(
        self, mock_dbs: MagicMock, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_dbs.return_value = ["inventory"]
        mock_status.return_value = []

        wrapped = dolt_autocommit(_ok_view)
        wrapped(auth_request)

        mock_commit.assert_not_called()

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    @patch("django_dolt.decorators.get_dolt_databases")
    def test_skips_on_error_response(
        self, mock_dbs: MagicMock, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_dbs.return_value = ["inventory"]

        wrapped = dolt_autocommit(_error_view)
        response = wrapped(auth_request)

        assert response.status_code == 500
        mock_status.assert_not_called()
        mock_commit.assert_not_called()

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    @patch("django_dolt.decorators.get_dolt_databases")
    def test_commits_on_redirect(
        self, mock_dbs: MagicMock, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_dbs.return_value = ["inventory"]
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(_redirect_view)
        response = wrapped(auth_request)

        assert response.status_code == 302
        mock_commit.assert_called_once()

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_using_single_db(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(_ok_view, using="orders")
        wrapped(auth_request)

        mock_status.assert_called_once_with(exclude_ignored=True, using="orders")
        mock_commit.assert_called_once()
        assert mock_commit.call_args.kwargs["using"] == "orders"

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_using_multiple_dbs(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(_ok_view, using=["inventory", "orders"])
        wrapped(auth_request)

        assert mock_commit.call_count == 2

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_callable_message(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(
            _ok_view,
            using="inventory",
            message=lambda r: f"Changed by {r.user.username}",
        )
        wrapped(auth_request)

        assert mock_commit.call_args.kwargs["message"] == "Changed by testuser"

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_custom_author_string(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(
            _ok_view, using="inventory", author="Bot <bot@example.com>",
        )
        wrapped(auth_request)

        assert mock_commit.call_args.kwargs["author"] == "Bot <bot@example.com>"

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_suppress_errors_true(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]
        mock_commit.side_effect = Exception("db error")

        wrapped = dolt_autocommit(_ok_view, using="inventory", suppress_errors=True)
        response = wrapped(auth_request)

        assert response.status_code == 200  # view response is preserved

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_suppress_errors_false(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]
        mock_commit.side_effect = Exception("db error")

        wrapped = dolt_autocommit(_ok_view, using="inventory", suppress_errors=False)

        with pytest.raises(Exception, match="db error"):
            wrapped(auth_request)

    def test_preserves_function_metadata(self) -> None:
        @dolt_autocommit(using="inventory")
        def my_named_view(request: HttpRequest) -> HttpResponse:
            """My docstring."""
            return HttpResponse("ok")

        assert my_named_view.__name__ == "my_named_view"
        assert my_named_view.__doc__ == "My docstring."

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_custom_commit_on_predicate(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        """Custom commit_on that only allows 200."""
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]

        wrapped = dolt_autocommit(
            _redirect_view,
            using="inventory",
            commit_on=lambda r: r.status_code == 200,
        )
        wrapped(auth_request)

        mock_commit.assert_not_called()

    @patch("django_dolt.decorators.services.dolt_add_and_commit")
    @patch("django_dolt.decorators.services.dolt_status")
    def test_bare_decorator_syntax(
        self, mock_status: MagicMock, mock_commit: MagicMock,
        auth_request: HttpRequest,
    ) -> None:
        """@dolt_autocommit without parens should work."""
        mock_status.return_value = [{"table_name": "t", "status": "modified"}]
        mock_commit.return_value = "abc123"

        @dolt_autocommit
        def view(request: HttpRequest) -> HttpResponse:
            return HttpResponse("ok")

        with patch("django_dolt.decorators.get_dolt_databases", return_value=["db1"]):
            view(auth_request)

        mock_commit.assert_called_once()
