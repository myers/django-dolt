# django-dolt

Django integration for [Dolt](https://www.dolthub.com/) version-controlled databases.

## Features

- **Service layer** - Python API for Dolt operations (add, commit, push, pull, status, log)
- **Management commands** - CLI tools for database version control
- **Admin integration** - View commit history and pull from remote in Django admin

## Requirements

- Python 3.12+
- Django 5.0+
- A Dolt database

## Installation

```bash
pip install django-dolt
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "django_dolt",
]
```

## Usage

### Service Layer

```python
from django_dolt import (
    dolt_add,
    dolt_commit,
    dolt_status,
    dolt_log,
    dolt_push,
    dolt_pull,
)

# Stage changes
dolt_add("my_table")  # Stage specific table
dolt_add()            # Stage all tables

# Commit
commit_hash = dolt_commit("Add new features", author="Dev <dev@example.com>")

# Check status
status = dolt_status()  # Returns list of changed tables
for change in status:
    print(f"{change['table_name']}: {change['status']}")

# View history
commits = dolt_log(limit=10)
for commit in commits:
    print(f"{commit['commit_hash'][:8]} - {commit['message']}")

# Push to remote
dolt_push(remote="origin", branch="main")

# Pull from remote
dolt_pull(remote="origin")
```

### Management Commands

```bash
# Show database status
python manage.py dolt_status
python manage.py dolt_status --log 5  # Show 5 recent commits

# Commit and push changes
python manage.py dolt_sync "Update data"
python manage.py dolt_sync --force     # Force push
python manage.py dolt_sync --no-push   # Commit only

# Pull from remote
python manage.py dolt_pull
python manage.py dolt_pull --fetch-only  # Fetch without merge
```

### Admin Integration

Option 1: Use the provided admin site:

```python
# urls.py
from django_dolt.admin import DoltAdminSite

admin_site = DoltAdminSite()

urlpatterns = [
    path("admin/", admin_site.urls),
]
```

Option 2: Add Dolt views to existing admin:

```python
# urls.py
from django.contrib import admin
from django_dolt.admin import get_dolt_admin_urls

urlpatterns = [
    path("admin/", admin.site.urls),
] + get_dolt_admin_urls(admin.site)
```

Then navigate to `/admin/dolt/commits/` to view commit history.

## Configuration

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
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/django_dolt

# Linting
ruff check src/django_dolt
```

## License

MIT
