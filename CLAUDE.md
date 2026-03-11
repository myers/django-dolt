# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-dolt is a Django integration package for Dolt version-controlled databases. It provides a Python API, management commands, admin integration, and view decorators for Dolt's git-like database operations (commit, push, pull, etc.). Requires Python 3.12+ and Django 5.0+.

## Development Commands

We use `uv` exclusively for Python package management. Never use `pip` directly.

```bash
uv pip install -e ".[dev]"        # Install dev dependencies

bin/test                           # Run all tests (auto-starts Dolt Docker container)
bin/test src/django_dolt/tests/test_services.py
bin/test src/django_dolt/tests/test_services.py::TestDoltCommit::test_commit_with_changes

mypy src/django_dolt               # Type checking (strict mode, django-stubs)
ruff check src/django_dolt         # Linting
```

Tests require Docker. The `conftest.py` automatically runs `docker compose up -d` to start a Dolt SQL server on port 8906 and tears it down after. If the container is already running, it reuses it.

## Architecture

### Two-layer design: models own all DB access, services own business logic

**`models.py`** — All database interaction lives here:
- Module-level `dolt_*()` functions for stored procedures (`CALL DOLT_ADD`, `CALL DOLT_COMMIT`, etc.)
- Read-only unmanaged models mapped to Dolt system tables (`dolt_branches`, `dolt_log`, `dolt_status`, `dolt_ignore`, `dolt_remotes`)
- Custom managers with query methods (`BranchManager.active_branch()`, `StatusManager.current()`, `CommitManager.recent()`, etc.)
- `create_proxy_models(db_alias)` factory for per-database admin registration

**`services.py`** — Business logic only, no `connections` import, no raw SQL:
- Wraps model functions with error handling and exception hierarchy (`DoltError` → `DoltCommitError`, `DoltPushError`, `DoltPullError`)
- Builds argument lists for push/pull/fetch (env var defaults, `--force`, `--user` flags)
- `dolt_add_and_commit()` uses Dolt's `-A` flag for atomic stage+commit (avoids race condition)
- "nothing to commit" → returns `None` instead of raising

### Import pattern: lazy imports to avoid AppRegistryNotReady

`__init__.py` eagerly imports services (no app registry dependency) but lazy-loads models via `__getattr__`. Inside `services.py`, every function does `from django_dolt import models` as a lazy import in the function body to break the circular import chain during app loading.

### Multi-database support

Every function accepts `using: str | None = None`. The `DOLT_DATABASES` setting lists database aliases. `apps.py` auto-registers admin views for each database during `ready()`. Proxy models (`Branch_{alias}`, `Commit_{alias}`, `Remote_{alias}`) allow per-database admin registration.

### Admin integration (`admin.py`)

- `DoltAdminSite` — Full admin site with Dolt views and sidebar grouping by database
- `DoltAdminMixin` / `DoltMultiDBAdminMixin` — Mixins to add Dolt views to existing admin
- `DoltCommitMixin` — Adds "Save and commit" button to model change forms
- `register_branch_extension(db_alias, config)` — Extension point for custom branch admin behavior
- Status view (`/admin/dolt/status/{db_alias}/`) supports GET (view) and POST (commit, superuser-only)

### View decorators (`decorators.py`)

`@dolt_autocommit` — Auto-commits after view execution. Supports parameterized and bare usage, callable message/author, and a `commit_on` predicate.

### Test configuration

- `tests/settings.py`: SQLite for "default", three Dolt aliases ("dolt", "dolt1", "dolt2") on localhost:8906
- `tests/conftest.py`: Manages Docker lifecycle, overrides `django_db_setup` to only create SQLite DB
- `dolt_db` fixture in `test_services.py`: Creates/drops a fresh database per test, rewires a connection alias
- Mock-based tests patch at the `django_dolt.models` level (e.g., `@patch("django_dolt.models.dolt_push")`)

## Environment Variables

- `DOLT_REMOTE_USER` — Username for remote authentication (read by services layer)
- `DOLT_REMOTE_PASSWORD` — Must be set at Dolt server level for push operations
