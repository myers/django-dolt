# django-dolt

Django integration for [Dolt](https://www.dolthub.com/) version-controlled databases, with multi-database support.

## Features

- **Service layer** - Python API for Dolt operations (add, commit, push, pull, diff, status, log)
- **Management commands** - CLI tools for database version control
- **Admin integration** - Browse branches, commits, remotes, and status; commit from the admin UI
- **View decorator** - `@dolt_autocommit` for automatic commits after view execution
- **Multi-database support** - Manage multiple Dolt databases from one Django project

## Requirements

- Python 3.12+
- Django 5.0+
- A Dolt database (speaks MySQL wire protocol)
- A MySQL client library (`mysqlclient` or `pymysql`)

## Installation

```bash
pip install django-dolt
```

Add to `INSTALLED_APPS` and configure your Dolt databases:

```python
INSTALLED_APPS = [
    ...
    "django_dolt",
]

DATABASES = {
    "default": { ... },
    "dolt": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": "my_dolt_db",
        "HOST": "127.0.0.1",
        "PORT": "3306",
        "USER": "root",
        "PASSWORD": "...",
    },
}

# Tell django-dolt which database aliases are Dolt databases
DOLT_DATABASES = ["dolt"]
```

## Usage

### Service Layer

```python
from django_dolt import (
    dolt_add,
    dolt_commit,
    dolt_add_and_commit,
    dolt_status,
    dolt_log,
    dolt_diff,
    dolt_push,
    dolt_pull,
)

# Stage and commit atomically (recommended)
commit_hash = dolt_add_and_commit(
    "Add new features",
    author="Dev <dev@example.com>",
    using="dolt",
)
# Returns None if nothing to commit

# Or stage and commit separately
dolt_add("my_table", using="dolt")  # Stage specific table
dolt_add(using="dolt")              # Stage all tables
commit_hash = dolt_commit("Update data", using="dolt")

# Check status
status = dolt_status(using="dolt")
for change in status:
    print(f"{change['table_name']}: {change['status']} (staged={change['staged']})")

# View history
commits = dolt_log(limit=10, using="dolt")
for commit in commits:
    print(f"{commit['commit_hash'][:8]} - {commit['message']}")

# View diff
changes = dolt_diff(from_ref="HEAD~1", to_ref="HEAD", using="dolt")

# Push to remote
dolt_push(remote="origin", branch="main", using="dolt")

# Pull from remote
dolt_pull(remote="origin", using="dolt")
```

All service functions accept a `using` keyword argument to specify which database alias to operate on.

### View Decorator

Auto-commit after successful view execution:

```python
from django_dolt import dolt_autocommit

@dolt_autocommit(using="dolt")
def my_view(request):
    # ... modify data ...
    return HttpResponse("OK")

# With dynamic message and author
@dolt_autocommit(
    message=lambda req: f"Update by {req.user}",
    author=lambda req: f"{req.user.get_full_name()} <{req.user.email}>",
    using="dolt",
)
def my_view(request):
    ...

# Only commit when a condition is met
@dolt_autocommit(commit_on=lambda req, resp: resp.status_code == 200, using="dolt")
def my_view(request):
    ...
```

### Management Commands

```bash
# Show database status
python manage.py dolt_status
python manage.py dolt_status --database dolt --log 5

# Commit and push changes
python manage.py dolt_sync "Update data"
python manage.py dolt_sync --database dolt --force
python manage.py dolt_sync --no-push  # Commit only

# Pull from remote
python manage.py dolt_pull
python manage.py dolt_pull --database dolt --fetch-only
```

### Admin Integration

**Option 1: Use the full Dolt admin site** (recommended):

```python
# urls.py
from django_dolt.admin import DoltAdminSite

admin_site = DoltAdminSite()

urlpatterns = [
    path("admin/", admin_site.urls),
]
```

```python
# settings.py
DOLT_AUTO_REGISTER_ADMIN = False  # Disable auto-registration on default admin
```

**Option 2: Add Dolt views to your existing admin:**

```python
# admin.py
from django.contrib.admin import AdminSite
from django_dolt.admin import DoltAdminMixin

class MyAdminSite(DoltAdminMixin, AdminSite):
    pass
```

The admin provides:
- Branch, commit, and remote browsing per database
- Status view with ability to commit (superusers only) at `/admin/dolt/status/{db_alias}/`
- Sidebar grouping by database when using `DoltAdminSite`

**Save and commit from model forms:**

```python
from django_dolt import DoltCommitMixin

class MyModelAdmin(DoltCommitMixin, admin.ModelAdmin):
    dolt_database = "dolt"  # Which database to commit to
```

This adds a "Save and commit" button to the change form.

## Demo Application

The `demo/` directory contains a fake e-commerce app demonstrating multi-database Dolt integration with two independent version-controlled databases:

- **Inventory database** — Categories, products, and product comments
- **Orders database** — Customers, orders, and order items

The standard Django tables (auth, sessions, etc.) live in SQLite or Postgres as usual, while data you want to version control lives in your Dolt databases. A database router directs models to the right backend.

The demo showcases:
- Multi-database routing with per-database version history
- `DoltAdminSite` with sidebar grouping by database
- `@dolt_autocommit` on a product comment view
- `DoltCommitMixin` for "Save and commit" in admin forms
- Dashboard views showing working set status and commit history

```bash
docker compose up -d                # Start Dolt server
cd demo
uv pip install -e "..[demo]"
python manage.py setup_demo         # Create databases, migrate, seed data
python manage.py createsuperuser
python manage.py runserver
```

Then visit `http://localhost:8000/` for the app or `http://localhost:8000/admin/` for the admin.

## Configuration

### Settings

- `DOLT_DATABASES` - List of database aliases that are Dolt databases
- `DOLT_ADMIN_EXCLUDE` - List of database aliases to skip during admin auto-registration
- `DOLT_AUTO_REGISTER_ADMIN` - Set to `False` to disable auto-registration on `admin.site` during `ready()`. Use when providing a custom admin site.

### Environment Variables

- `DOLT_REMOTE_USER` - Username for remote authentication
- `DOLT_REMOTE_PASSWORD` - Password (must be set at Dolt server level)

### dolt_ignore

To exclude tables from version control, add patterns to the `dolt_ignore` table:

```sql
INSERT INTO dolt_ignore (pattern, ignored) VALUES ('django_%', 1);
INSERT INTO dolt_ignore (pattern, ignored) VALUES ('auth_%', 1);
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests (requires Docker — auto-starts Dolt container)
bin/test
bin/test src/django_dolt/tests/test_services.py

# Type checking
uv run mypy src/django_dolt

# Linting
uv run ruff check src/django_dolt
```

## License

MIT

## Inspirations
- https://www.dolthub.com/blog/2021-06-09-running-django-on-dolt/
- https://www.dolthub.com/blog/2021-08-27-django-dolt-2/
- https://www.dolthub.com/blog/2024-01-31-dolt-django/
