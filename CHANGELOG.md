# Changelog

## 1.0.0 (2026-03-09)

Initial release.

### Features

- **Service layer** — `dolt_add`, `dolt_commit`, `dolt_status`, `dolt_log`, `dolt_diff`, `dolt_push`, `dolt_pull`, `dolt_fetch`, `dolt_branch_list`, `dolt_current_branch`, `dolt_remotes`, `dolt_add_remote`, `dolt_add_and_commit`, `get_ignored_tables`
- **Management commands** — `dolt_status`, `dolt_sync`, `dolt_pull`
- **Admin integration** — `DoltAdminSite`, `get_dolt_admin_urls()`, branch extension registry (`register_branch_extension`)
- **Multi-database support** — all service functions accept a `using` parameter
- **Django model proxies** — `Branch`, `Commit`, `Remote` models backed by Dolt system tables (`dolt_branches`, `dolt_log`, `dolt_remotes`)
- **Per-database proxy models** — `create_proxy_models()` for multi-database admin registration
- **`--user` auth support** — `dolt_push`, `dolt_pull`, `dolt_fetch` support remote authentication
