"""
Django admin integration for Dolt version control.

Provides an extended admin site with Dolt commit history and pull functionality.
"""

from __future__ import annotations

from typing import cast

from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse

from django_dolt import services


class DoltAdminMixin:
    """Mixin to add Dolt views to an existing admin site."""

    def get_urls(self) -> list[URLPattern]:
        """Add Dolt-specific URLs to admin."""
        urls = super().get_urls()  # type: ignore[misc]
        dolt_urls: list[URLPattern] = [
            path(
                "dolt/commits/",
                self.admin_view(self.dolt_commits_view),  # type: ignore[attr-defined]
                name="dolt_commits",
            ),
            path(
                "dolt/pull/",
                self.admin_view(self.dolt_pull_view),  # type: ignore[attr-defined]
                name="dolt_pull",
            ),
        ]
        return dolt_urls + cast(list[URLPattern], urls)

    def dolt_commits_view(self, request: HttpRequest) -> TemplateResponse:
        """Display Dolt commit history."""
        commits = []
        status_info = []

        # Get commit history
        raw_commits = services.dolt_log(limit=50)
        for commit in raw_commits:
            commits.append(
                {
                    "hash": commit["commit_hash"][:8],
                    "full_hash": commit["commit_hash"],
                    "author": f"{commit['committer']} <{commit['email']}>",
                    "date": commit["date"],
                    "message": commit["message"],
                    "message_lines": commit["message"].split("\n"),
                }
            )

        # Get current status (excluding ignored tables)
        status = services.dolt_status(exclude_ignored=True)
        for row in status:
            status_info.append(
                {
                    "table": row["table_name"],
                    "staged": row.get("staged", 0),
                    "status": row.get("status", ""),
                }
            )

        # Get current branch
        current_branch = services.dolt_current_branch()

        # Get ignored patterns for display
        ignored_patterns = services.get_ignored_tables()

        context = {
            **self.each_context(request),  # type: ignore[attr-defined]
            "title": "Dolt Commit History",
            "commits": commits,
            "status": status_info,
            "current_branch": current_branch,
            "ignored_patterns": ignored_patterns,
        }
        return TemplateResponse(
            request, "admin/django_dolt/commit_history.html", context
        )

    def dolt_pull_view(self, request: HttpRequest) -> HttpResponse:
        """Handle pull from remote."""
        if request.method == "POST":
            remote = request.POST.get("remote", "origin")
            branch = request.POST.get("branch") or None

            try:
                result = services.dolt_pull(remote, branch)
                self.message_user(request, f"Pull successful: {result}")  # type: ignore[attr-defined]
            except services.DoltPullError as e:
                self.message_user(  # type: ignore[attr-defined]
                    request,
                    f"Pull failed: {e}",
                    level="error",
                )

            return HttpResponseRedirect(reverse("admin:dolt_commits"))

        # GET request - show pull form
        current_branch = services.dolt_current_branch()
        remotes = services.dolt_remotes()

        context = {
            **self.each_context(request),  # type: ignore[attr-defined]
            "title": "Pull from Remote",
            "current_branch": current_branch,
            "remotes": remotes,
        }
        return TemplateResponse(request, "admin/django_dolt/pull.html", context)


class DoltAdminSite(DoltAdminMixin, admin.AdminSite):  # type: ignore[misc]
    """Extended admin site with Dolt version control integration."""

    site_header = "Django Administration (Dolt)"
    site_title = "Django Dolt Admin"
    index_title = "Site Administration"


# Convenience function to get admin URLs for use with existing admin sites
def get_dolt_admin_urls(admin_site: admin.AdminSite) -> list[URLPattern]:
    """Get Dolt admin URLs for use with an existing admin site.

    Usage:
        from django.contrib import admin
        from django_dolt.admin import get_dolt_admin_urls

        urlpatterns = [
            path('admin/', admin.site.urls),
        ] + get_dolt_admin_urls(admin.site)
    """

    def dolt_commits_view(request: HttpRequest) -> TemplateResponse:
        commits = []
        status_info = []

        raw_commits = services.dolt_log(limit=50)
        for commit in raw_commits:
            commits.append(
                {
                    "hash": commit["commit_hash"][:8],
                    "full_hash": commit["commit_hash"],
                    "author": f"{commit['committer']} <{commit['email']}>",
                    "date": commit["date"],
                    "message": commit["message"],
                    "message_lines": commit["message"].split("\n"),
                }
            )

        status = services.dolt_status(exclude_ignored=True)
        for row in status:
            status_info.append(
                {
                    "table": row["table_name"],
                    "staged": row.get("staged", 0),
                    "status": row.get("status", ""),
                }
            )

        current_branch = services.dolt_current_branch()
        ignored_patterns = services.get_ignored_tables()

        context = {
            **admin_site.each_context(request),
            "title": "Dolt Commit History",
            "commits": commits,
            "status": status_info,
            "current_branch": current_branch,
            "ignored_patterns": ignored_patterns,
        }
        return TemplateResponse(
            request, "admin/django_dolt/commit_history.html", context
        )

    def dolt_pull_view(request: HttpRequest) -> HttpResponse:
        if request.method == "POST":
            remote = request.POST.get("remote", "origin")
            branch = request.POST.get("branch") or None

            try:
                result = services.dolt_pull(remote, branch)
                messages.success(request, f"Pull successful: {result}")
            except services.DoltPullError as e:
                messages.error(request, f"Pull failed: {e}")

            return HttpResponseRedirect(reverse("admin:dolt_commits"))

        current_branch = services.dolt_current_branch()
        remotes = services.dolt_remotes()

        context = {
            **admin_site.each_context(request),
            "title": "Pull from Remote",
            "current_branch": current_branch,
            "remotes": remotes,
        }
        return TemplateResponse(request, "admin/django_dolt/pull.html", context)

    return [
        path(
            "admin/dolt/commits/",
            admin_site.admin_view(dolt_commits_view),
            name="dolt_commits",
        ),
        path(
            "admin/dolt/pull/",
            admin_site.admin_view(dolt_pull_view),
            name="dolt_pull",
        ),
    ]
