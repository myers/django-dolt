"""View decorators for automatic Dolt commits."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponse

from django_dolt import services
from django_dolt.dolt_databases import get_dolt_databases

logger = logging.getLogger("django_dolt")


def get_author_from_request(request: HttpRequest) -> str:
    """Build a Dolt author string from the request's authenticated user.

    Returns "Name <email>" for authenticated users, or a default for anonymous.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        name = user.get_full_name() or user.username
        email = user.email or f"{user.username}@localhost"
        return f"{name} <{email}>"
    return "Django <django@localhost>"


def _default_should_commit(response: HttpResponse) -> bool:
    """Commit on 2xx and 3xx responses (covers POST-redirect-GET)."""
    return 200 <= response.status_code < 400


def dolt_autocommit(
    fn: Callable[..., HttpResponse] | None = None,
    *,
    using: str | list[str] | None = None,
    message: str | Callable[[HttpRequest], str] = "Auto-commit",
    author: str | Callable[[HttpRequest], str] | None = None,
    commit_on: Callable[[HttpResponse], bool] | None = None,
    suppress_errors: bool = True,
) -> Any:
    """Decorator that auto-commits Dolt changes after a view returns.

    After the wrapped view executes, checks each specified Dolt database
    for uncommitted changes and commits them as the current user.

    Can be used with or without arguments::

        @dolt_autocommit
        def my_view(request):
            ...

        @dolt_autocommit(using="inventory", message="Updated inventory")
        def my_view(request):
            ...

    Args:
        using: Database alias(es) to commit to. ``None`` commits to all
            detected Dolt databases that have uncommitted changes.
        message: Commit message string, or a callable ``(request) -> str``.
        author: Author string or callable ``(request) -> str``. Defaults
            to deriving the author from ``request.user``.
        commit_on: Predicate ``(response) -> bool`` controlling when to
            commit. Defaults to committing on 2xx and 3xx responses.
        suppress_errors: If ``True`` (default), log commit errors instead
            of letting them propagate to the caller.
    """
    if commit_on is None:
        commit_on = _default_should_commit

    def decorator(view_fn: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @functools.wraps(view_fn)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            response = view_fn(request, *args, **kwargs)

            if not commit_on(response):
                return response

            # Resolve databases to check
            if using is None:
                db_list = get_dolt_databases()
            elif isinstance(using, str):
                db_list = [using]
            else:
                db_list = list(using)

            # Resolve author
            if author is None:
                resolved_author = get_author_from_request(request)
            elif callable(author):
                resolved_author = author(request)
            else:
                resolved_author = author

            # Resolve message
            if callable(message):
                resolved_message = message(request)
            else:
                resolved_message = message

            for db_alias in db_list:
                try:
                    status = services.dolt_status(
                        exclude_ignored=True,
                        using=db_alias,
                    )
                    if not status:
                        continue
                    services.dolt_add_and_commit(
                        message=resolved_message,
                        author=resolved_author,
                        using=db_alias,
                    )
                except Exception:
                    if suppress_errors:
                        logger.exception(
                            "dolt_autocommit: failed to commit to %s",
                            db_alias,
                        )
                    else:
                        raise

            return response

        return wrapper

    # Support both @dolt_autocommit and @dolt_autocommit(...)
    if fn is not None:
        return decorator(fn)
    return decorator
