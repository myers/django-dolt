# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-dolt is a Django integration package for Dolt version-controlled databases. It provides a Python API, management commands, and admin integration for Dolt's git-like database operations (commit, push, pull, etc.).

## Development Commands

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run a single test file
pytest src/django_dolt/tests/test_services.py

# Run a specific test
pytest src/django_dolt/tests/test_services.py::TestDoltCommit::test_commit_returns_hash

# Type checking
mypy src/django_dolt

# Linting
ruff check src/django_dolt
```

## Architecture

### Service Layer (`services.py`)
Core module containing all Dolt database operations. Functions execute Dolt commands via Django's database connection using `CALL DOLT_*` stored procedures and Dolt system tables (`dolt_status`, `dolt_log`, `dolt_branches`, `dolt_ignore`, `dolt_remotes`).

Key functions: `dolt_add`, `dolt_commit`, `dolt_status`, `dolt_log`, `dolt_push`, `dolt_pull`

Custom exceptions: `DoltError` (base), `DoltCommitError`, `DoltPushError`, `DoltPullError`

### Management Commands (`management/commands/`)
- `dolt_status` - Show database status and recent commits
- `dolt_sync` - Stage, commit, and optionally push changes
- `dolt_pull` - Pull from remote

### Admin Integration (`admin.py`)
Two integration patterns:
1. `DoltAdminSite` - Extended admin site with Dolt views built-in
2. `get_dolt_admin_urls()` - Add Dolt views to existing admin site

Admin views: `/admin/dolt/commits/` (commit history) and `/admin/dolt/pull/` (pull form)

### Test Configuration
Tests use `tests/settings.py` with SQLite in-memory database. The service layer tests mock `django.db.connection` since actual Dolt operations require a Dolt database.

## Environment Variables

- `DOLT_REMOTE_USER` - Username for remote authentication
- `DOLT_REMOTE_PASSWORD` - Must be set at Dolt server level for push operations
