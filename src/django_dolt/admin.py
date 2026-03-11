"""
Django admin integration for Dolt version control.

Provides an extended admin site with Dolt commit history and pull functionality,
plus read-only ModelAdmin classes for Dolt system tables.
"""

from typing import Any, cast

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import router
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse

from django_dolt import services
from django_dolt.decorators import get_author_from_request
from django_dolt.dolt_databases import get_dolt_databases
from django_dolt.models import Branch, Commit, Remote


def _get_dolt_db_for_model(model: type) -> str | None:
    """Get the Dolt database alias for a model using Django's router."""
    db_alias = router.db_for_write(model)
    if db_alias and db_alias in get_dolt_databases():
        return db_alias
    return None


class DoltCommitMixin:
    """ModelAdmin mixin that adds a 'Save and commit' button to change forms.

    When the user clicks 'Save and commit', the model is saved normally
    and then all uncommitted changes in that model's Dolt database are
    committed with the admin user as the author.

    Uses Django's database router to determine which Dolt database the
    model belongs to. Models not routed to a Dolt database are unaffected.

    Usage:
        from django_dolt.admin import DoltCommitMixin

        @admin.register(MyModel)
        class MyModelAdmin(DoltCommitMixin, admin.ModelAdmin):
            pass
    """

    change_form_template = "admin/django_dolt/change_form_dolt.html"

    def _do_dolt_commit(self, request: HttpRequest, obj: Any) -> None:
        db_alias = _get_dolt_db_for_model(type(obj))
        if not db_alias:
            return
        author = get_author_from_request(request)
        try:
            commit_hash = services.dolt_add_and_commit(
                message=f"Update {type(obj).__name__}: {obj}",
                author=author,
                using=db_alias,
            )
            if commit_hash:
                messages.success(request, f"Committed to {db_alias}: {commit_hash[:8]}")
            else:
                messages.info(request, f"No changes to commit in {db_alias}")
        except Exception as e:
            messages.error(request, f"Commit failed: {e}")

    def response_add(
        self, request: HttpRequest, obj: Any, post_url_continue: str | None = None
    ) -> HttpResponse:
        if "_save_and_commit" in request.POST:
            response = super().response_add(request, obj, post_url_continue)  # type: ignore[misc]
            self._do_dolt_commit(request, obj)
            return response
        return super().response_add(request, obj, post_url_continue)  # type: ignore[misc]

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        if "_save_and_commit" in request.POST:
            response = super().response_change(request, obj)  # type: ignore[misc]
            self._do_dolt_commit(request, obj)
            return response
        return super().response_change(request, obj)  # type: ignore[misc]


# Extension registry: db_alias -> extension config dict
_branch_extensions: dict[str, dict] = {}


def register_branch_extension(db_alias: str, extension: dict) -> None:
    """Register an extension for a database's Branch admin.

    Extension dict can contain:
      - get_extra_urls: callable(model_admin) -> list[URLPattern]
      - get_changelist_context: callable(request, db_alias) -> dict
      - changelist_template: str (template path to include in changelist)
    """
    _branch_extensions[db_alias] = extension


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
        # Add status and diff URLs for each Dolt database
        for db_alias in get_dolt_databases():
            dolt_urls.append(
                path(
                    f"dolt/status/{db_alias}/",
                    self.admin_view(_make_status_view(db_alias)),  # type: ignore[attr-defined]
                    name=f"dolt_status_{db_alias}",
                )
            )
            dolt_urls.append(
                path(
                    f"dolt/status/{db_alias}/diff/<str:table_name>/",
                    self.admin_view(_make_diff_view(db_alias)),  # type: ignore[attr-defined]
                    name=f"dolt_diff_{db_alias}",
                )
            )
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
            if not request.user.is_superuser:
                raise PermissionDenied
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


class DoltMultiDBAdminMixin:
    """Mixin to reorganize Dolt models by database in the admin sidebar.

    Instead of showing:
        DOLT VERSION CONTROL
        - Branches (Inventory Db)
        - Branches (Orders Db)
        - Commits (Inventory Db)
        ...

    This shows:
        INVENTORY DB (DOLT)
        - Branches
        - Commits
        - Remotes
    """

    def get_app_list(
        self, request: HttpRequest, app_label: str | None = None
    ) -> list[dict[str, Any]]:
        """Reorganize Dolt models by database and inject status links."""
        app_list = super().get_app_list(request, app_label)  # type: ignore[misc]

        # Find the django_dolt app
        dolt_app = None
        other_apps = []
        for app in app_list:
            if app.get("app_label") == "django_dolt":
                dolt_app = app
            else:
                other_apps.append(app)

        if not dolt_app or not dolt_app.get("models"):
            return app_list

        # Group models by database
        db_groups: dict[str, list[dict[str, Any]]] = {}
        for model in dolt_app["models"]:
            # Model names are like "Branch_inventory_db", "Commit_orders_db"
            name = model.get("object_name", "")
            parts = name.split("_", 1)
            if len(parts) == 2:
                model_type, db_suffix = parts
                # e.g., "inventory_db" -> "Inventory Db"
                db_display = db_suffix.replace("_", " ").title()

                if db_suffix not in db_groups:
                    db_groups[db_suffix] = []

                # Create a cleaned model entry with simple name
                cleaned_model = model.copy()
                cleaned_model["name"] = (
                    model_type + "s"
                    if not model_type.endswith("s")
                    else model_type + "es"
                )
                # Use verbose_name_plural if available
                if "Branches" in str(model.get("name", "")):
                    cleaned_model["name"] = "Branches"
                elif "Commits" in str(model.get("name", "")):
                    cleaned_model["name"] = "Commits"
                elif "Remotes" in str(model.get("name", "")):
                    cleaned_model["name"] = "Remotes"

                db_groups[db_suffix].append(cleaned_model)

        # Create separate app entries for each database
        dolt_apps = []
        dolt_databases = get_dolt_databases()
        for db_suffix, models in sorted(db_groups.items()):
            db_display = db_suffix.replace("_", " ").title()
            # Inject a Status link if this is a known Dolt database
            if db_suffix in dolt_databases:
                if not any(m.get("name") == "Status" for m in models):
                    try:
                        status_url = reverse("admin:dolt_status_" + db_suffix)
                        models.insert(
                            0,
                            {
                                "name": "Status",
                                "object_name": f"Status_{db_suffix}",
                                "admin_url": status_url,
                                "view_only": True,
                            },
                        )
                    except Exception:
                        pass
            dolt_apps.append(
                {
                    "name": f"{db_display} (Dolt)",
                    "app_label": f"django_dolt_{db_suffix}",
                    "app_url": dolt_app.get("app_url", ""),
                    "has_module_perms": dolt_app.get("has_module_perms", True),
                    "models": sorted(models, key=lambda m: m.get("name", "")),
                }
            )

        return other_apps + dolt_apps


class DoltAdminSite(DoltMultiDBAdminMixin, DoltAdminMixin, admin.AdminSite):  # type: ignore[misc]
    """Extended admin site with Dolt version control integration."""

    site_header = "Django Administration (Dolt)"
    site_title = "Django Dolt Admin"
    index_title = "Site Administration"


# -----------------------------------------------------------------------------
# Read-only ModelAdmin classes for Dolt system tables
# -----------------------------------------------------------------------------


class ReadOnlyModelAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Base class for read-only model admins."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class BranchAdmin(ReadOnlyModelAdmin):
    """Admin for viewing Dolt branches."""

    list_display = ["name", "hash_short", "latest_committer", "latest_commit_date"]
    search_fields = ["name", "latest_committer"]
    ordering = ["name"]

    @admin.display(description="Hash")
    def hash_short(self, obj: Branch) -> str:
        return obj.hash[:8]


class CommitAdmin(ReadOnlyModelAdmin):
    """Admin for viewing Dolt commit history."""

    list_display = ["hash_short", "committer", "date", "message_preview"]
    list_filter = ["committer"]
    search_fields = ["commit_hash", "committer", "message"]
    ordering = ["-date"]
    list_per_page = 50

    @admin.display(description="Hash")
    def hash_short(self, obj: Commit) -> str:
        return obj.commit_hash[:8]

    @admin.display(description="Message")
    def message_preview(self, obj: Commit) -> str:
        if len(obj.message) > 60:
            return obj.message[:60] + "..."
        return obj.message


class RemoteAdmin(ReadOnlyModelAdmin):
    """Admin for viewing Dolt remotes."""

    list_display = ["name", "url"]
    search_fields = ["name", "url"]
    ordering = ["name"]


def register_default_dolt_admin() -> None:
    """Register Dolt admin for the default database.

    Only call this if your default database is a Dolt database.
    For multi-database setups, use register_dolt_admin() instead.
    """
    admin.site.register(Branch, BranchAdmin)
    admin.site.register(Commit, CommitAdmin)
    admin.site.register(Remote, RemoteAdmin)


# -----------------------------------------------------------------------------
# Dynamic admin registration for multi-database support
# -----------------------------------------------------------------------------


def register_dolt_admin(db_alias: str) -> None:
    """Register admin classes for a specific Dolt database.

    Creates and registers ModelAdmin classes for the database-specific
    proxy models. Each database gets its own set of admin entries.

    Args:
        db_alias: Database alias from Django settings.
    """
    from django_dolt.models import create_proxy_models

    BranchProxy, CommitProxy, RemoteProxy = create_proxy_models(db_alias)

    class DynamicBranchAdmin(ReadOnlyModelAdmin):
        """Admin for viewing Dolt branches for a specific database."""

        list_display = ["name", "hash_short", "latest_committer", "latest_commit_date"]
        search_fields = ["name", "latest_committer"]
        ordering = ["name"]
        change_list_template = "admin/django_dolt/branch_changelist.html"

        @admin.display(description="Hash")
        def hash_short(self, obj: Branch) -> str:
            return obj.hash[:8]

        def get_queryset(self, request: HttpRequest) -> Any:
            return super().get_queryset(request).using(db_alias)

        def get_urls(self) -> list[URLPattern]:
            urls = super().get_urls()
            ext = _branch_extensions.get(db_alias)
            if ext and "get_extra_urls" in ext:
                extra = ext["get_extra_urls"](self)
                urls = extra + urls
            return urls

        def changelist_view(
            self, request: HttpRequest, extra_context: dict[str, Any] | None = None
        ) -> Any:
            extra_context = extra_context or {}
            ext = _branch_extensions.get(db_alias)
            if ext:
                if "get_changelist_context" in ext:
                    extra_context.update(
                        ext["get_changelist_context"](request, db_alias)
                    )
                if "changelist_template" in ext:
                    extra_context["branch_extension_template"] = ext[
                        "changelist_template"
                    ]
            return super().changelist_view(request, extra_context=extra_context)

    class DynamicCommitAdmin(ReadOnlyModelAdmin):
        """Admin for viewing Dolt commit history for a specific database."""

        list_display = ["hash_short", "committer", "date", "message_preview"]
        list_filter = ["committer"]
        search_fields = ["commit_hash", "committer", "message"]
        ordering = ["-date"]
        list_per_page = 50

        @admin.display(description="Hash")
        def hash_short(self, obj: Commit) -> str:
            return obj.commit_hash[:8]

        @admin.display(description="Message")
        def message_preview(self, obj: Commit) -> str:
            if len(obj.message) > 60:
                return obj.message[:60] + "..."
            return obj.message

        def get_queryset(self, request: HttpRequest) -> Any:
            return super().get_queryset(request).using(db_alias)

    class DynamicRemoteAdmin(ReadOnlyModelAdmin):
        """Admin for viewing Dolt remotes for a specific database."""

        list_display = ["name", "url"]
        search_fields = ["name", "url"]
        ordering = ["name"]

        def get_queryset(self, request: HttpRequest) -> Any:
            return super().get_queryset(request).using(db_alias)

    # Register the admin classes
    admin.site.register(BranchProxy, DynamicBranchAdmin)
    admin.site.register(CommitProxy, DynamicCommitAdmin)
    admin.site.register(RemoteProxy, DynamicRemoteAdmin)


def _make_status_view(db_alias: str) -> Any:
    """Create a status view function for a specific database."""

    def status_view(request: HttpRequest) -> HttpResponse:
        if request.method == "POST":
            if not request.user.is_superuser:
                raise PermissionDenied
            message = request.POST.get("message", "Manual commit")
            author = get_author_from_request(request)
            try:
                services.dolt_add(".", using=db_alias)
                result = services.dolt_commit(
                    message=message,
                    author=author,
                    using=db_alias,
                )
                if result:
                    messages.success(request, f"Committed to {db_alias}: {result[:8]}")
                else:
                    messages.info(request, f"No changes to commit in {db_alias}")
            except services.DoltError as e:
                err_msg = str(e)
                if "nothing to commit" in err_msg.lower():
                    messages.info(request, f"No changes to commit in {db_alias}")
                else:
                    messages.error(request, f"Commit failed: {e}")
            return HttpResponseRedirect(reverse("admin:dolt_status_" + db_alias))

        # GET: show status
        try:
            status = services.dolt_status(exclude_ignored=True, using=db_alias)
            for item in status:
                item["diff_url"] = reverse(
                    "admin:dolt_diff_" + db_alias,
                    kwargs={"table_name": item["table_name"]},
                )
        except Exception:
            status = []

        try:
            commits = services.dolt_log(limit=10, using=db_alias)
        except Exception:
            commits = []

        try:
            current_branch = services.dolt_current_branch(using=db_alias)
        except Exception:
            current_branch = "unknown"

        db_display = db_alias.replace("_", " ").title()
        context = {
            **admin.site.each_context(request),
            "title": f"{db_display} — Dolt Status",
            "db_alias": db_alias,
            "db_display": db_display,
            "current_branch": current_branch,
            "status": status,
            "can_commit": request.user.is_superuser,
            "commits": commits,
        }
        return TemplateResponse(request, "admin/django_dolt/status.html", context)

    return status_view


def _make_diff_view(db_alias: str) -> Any:
    """Create a table diff view function for a specific database."""

    def diff_view(request: HttpRequest, table_name: str) -> HttpResponse:
        try:
            diff_rows = services.dolt_diff(
                "HEAD", "WORKING", table_name, using=db_alias
            )
        except Exception:
            diff_rows = []

        # Process diff rows: extract column names and highlight changes
        columns: list[str] = []
        processed_rows: list[dict[str, Any]] = []
        if diff_rows:
            # Get base column names (strip from_/to_ prefix), skip commit metadata
            skip = {"commit", "commit_date"}
            seen: list[str] = []
            for key in diff_rows[0]:
                if key == "diff_type":
                    continue
                base = key.split("_", 1)[1] if key.startswith(("from_", "to_")) else key
                if base not in skip and base not in seen:
                    seen.append(base)
            columns = seen

            for row in diff_rows:
                cells = []
                for col in columns:
                    from_val = row.get(f"from_{col}")
                    to_val = row.get(f"to_{col}")
                    changed = from_val != to_val
                    cells.append(
                        {
                            "column": col,
                            "from_val": from_val,
                            "to_val": to_val,
                            "changed": changed,
                        }
                    )
                processed_rows.append(
                    {
                        "diff_type": row.get("diff_type", ""),
                        "cells": cells,
                    }
                )

        db_display = db_alias.replace("_", " ").title()
        status_url = reverse("admin:dolt_status_" + db_alias)
        context = {
            **admin.site.each_context(request),
            "title": f"{db_display} — Diff: {table_name}",
            "db_alias": db_alias,
            "db_display": db_display,
            "table_name": table_name,
            "columns": columns,
            "diff_rows": processed_rows,
            "status_url": status_url,
        }
        return TemplateResponse(request, "admin/django_dolt/diff.html", context)

    return diff_view
