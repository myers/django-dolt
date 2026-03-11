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
from django_dolt.models import Branch, Commit


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
        response: HttpResponse = super().response_add(request, obj, post_url_continue)  # type: ignore[misc]
        if "_save_and_commit" in request.POST:
            self._do_dolt_commit(request, obj)
        return response

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        response: HttpResponse = super().response_change(request, obj)  # type: ignore[misc]
        if "_save_and_commit" in request.POST:
            self._do_dolt_commit(request, obj)
        return response


# Extension registry: db_alias -> extension config dict
_branch_extensions: dict[str, dict[str, Any]] = {}


def register_branch_extension(db_alias: str, extension: dict[str, Any]) -> None:
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
        dolt_urls: list[URLPattern] = []
        # Add status and diff URLs for each Dolt database
        for db_alias in get_dolt_databases():
            dolt_urls.append(
                path(
                    f"dolt/status/{db_alias}/",
                    self.admin_view(_make_status_view(db_alias, site=self)),  # type: ignore[attr-defined, arg-type]
                    name=f"dolt_status_{db_alias}",
                )
            )
            dolt_urls.append(
                path(
                    f"dolt/status/{db_alias}/diff/<str:table_name>/",
                    self.admin_view(_make_diff_view(db_alias, site=self)),  # type: ignore[attr-defined, arg-type]
                    name=f"dolt_diff_{db_alias}",
                )
            )
        return dolt_urls + cast(list[URLPattern], urls)


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
        app_list: list[dict[str, Any]] = super().get_app_list(request, app_label)  # type: ignore[misc]

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
                plural_names = {
                    "Branch": "Branches",
                    "Commit": "Commits",
                    "Remote": "Remotes",
                }
                cleaned_model["name"] = plural_names.get(
                    model_type, model_type + "s"
                )

                db_groups[db_suffix].append(cleaned_model)

        # Create separate app entries for each database
        dolt_apps = []
        dolt_databases = get_dolt_databases()
        for db_suffix, models in sorted(db_groups.items()):
            db_display = db_suffix.replace("_", " ").title()
            # Inject a Status link if this is a known Dolt database
            if db_suffix in dolt_databases:
                if not any(m.get("name") == "Status" for m in models):
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
# Read-only ModelAdmin base classes
# -----------------------------------------------------------------------------


class ReadOnlyModelAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Base class for read-only model admins."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class BaseBranchAdmin(ReadOnlyModelAdmin):
    """Shared configuration for Branch admin views."""

    list_display = ["name", "hash_short", "latest_committer", "latest_commit_date"]
    search_fields = ["name", "latest_committer"]
    ordering = ["name"]

    @admin.display(description="Hash")
    def hash_short(self, obj: Branch) -> str:
        return obj.hash[:8]


class BaseCommitAdmin(ReadOnlyModelAdmin):
    """Shared configuration for Commit admin views."""

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


class BaseRemoteAdmin(ReadOnlyModelAdmin):
    """Shared configuration for Remote admin views."""

    list_display = ["name", "url"]
    search_fields = ["name", "url"]
    ordering = ["name"]


# -----------------------------------------------------------------------------
# Dynamic admin registration for multi-database support
# -----------------------------------------------------------------------------


def register_dolt_admin(db_alias: str, site: admin.AdminSite | None = None) -> None:
    """Register admin classes for a specific Dolt database.

    Creates and registers ModelAdmin classes for the database-specific
    proxy models. Each database gets its own set of admin entries.

    Args:
        db_alias: Database alias from Django settings.
        site: AdminSite to register with. Defaults to admin.site.
    """
    from django_dolt.models import create_proxy_models

    BranchProxy, CommitProxy, RemoteProxy = create_proxy_models(db_alias)

    class DynamicBranchAdmin(BaseBranchAdmin):
        """Admin for viewing Dolt branches for a specific database."""

        change_list_template = "admin/django_dolt/branch_changelist.html"

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

    class DynamicCommitAdmin(BaseCommitAdmin):
        """Admin for viewing Dolt commit history for a specific database."""

        def get_queryset(self, request: HttpRequest) -> Any:
            return super().get_queryset(request).using(db_alias)

    class DynamicRemoteAdmin(BaseRemoteAdmin):
        """Admin for viewing Dolt remotes for a specific database."""

        def get_queryset(self, request: HttpRequest) -> Any:
            return super().get_queryset(request).using(db_alias)

    # Register the admin classes
    target_site = site or admin.site
    target_site.register(BranchProxy, DynamicBranchAdmin)
    target_site.register(CommitProxy, DynamicCommitAdmin)
    target_site.register(RemoteProxy, DynamicRemoteAdmin)


def _make_status_view(db_alias: str, site: admin.AdminSite | None = None) -> Any:
    """Create a status view function for a specific database."""
    admin_site = site or admin.site

    def status_view(request: HttpRequest) -> HttpResponse:
        if request.method == "POST":
            if not request.user.is_superuser:
                raise PermissionDenied
            message = request.POST.get("message", "Manual commit")
            author = get_author_from_request(request)
            try:
                result = services.dolt_add_and_commit(
                    message=message,
                    author=author,
                    using=db_alias,
                )
                if result:
                    messages.success(request, f"Committed to {db_alias}: {result[:8]}")
                else:
                    messages.info(request, f"No changes to commit in {db_alias}")
            except services.DoltError as e:
                messages.error(request, f"Commit failed: {e}")
            return HttpResponseRedirect(reverse("admin:dolt_status_" + db_alias))

        # GET: show status
        status = services.dolt_status(exclude_ignored=True, using=db_alias)
        for item in status:
            item["diff_url"] = reverse(
                "admin:dolt_diff_" + db_alias,
                kwargs={"table_name": item["table_name"]},
            )

        commits = services.dolt_log(limit=10, using=db_alias)
        current_branch = services.dolt_current_branch(using=db_alias)

        db_display = db_alias.replace("_", " ").title()
        context = {
            **admin_site.each_context(request),
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


def _make_diff_view(db_alias: str, site: admin.AdminSite | None = None) -> Any:
    """Create a table diff view function for a specific database."""
    admin_site = site or admin.site

    def diff_view(request: HttpRequest, table_name: str) -> HttpResponse:
        if request.method != "GET":
            return HttpResponseRedirect(
                reverse("admin:dolt_status_" + db_alias)
            )

        diff_rows = services.dolt_diff(
            "HEAD", "WORKING", table_name, using=db_alias
        )

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
            **admin_site.each_context(request),
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
