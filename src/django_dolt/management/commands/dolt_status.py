"""
Django management command to show Dolt database status.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_dolt import services


class Command(BaseCommand):
    """Show Dolt database status without committing or pushing."""

    help = "Show Dolt database status without committing or pushing"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Show all tables including ignored ones",
        )
        parser.add_argument(
            "--log",
            type=int,
            default=0,
            metavar="N",
            help="Show N recent commits (default: 0, no commits shown)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        show_all: bool = options["all"]
        log_count: int = options["log"]

        self.stdout.write("Dolt Database Status")
        self.stdout.write("=" * 40)

        # Current branch
        branch = services.dolt_current_branch()
        self.stdout.write(f"\nBranch: {branch}")

        # Check for uncommitted changes
        status = services.dolt_status(exclude_ignored=not show_all)

        if status:
            self.stdout.write("\nUncommitted changes:")
            self.stdout.write(self._format_status(status))
        else:
            self.stdout.write("\nNo uncommitted changes")

        # Show ignored patterns
        ignored = services.get_ignored_tables()
        if ignored:
            self.stdout.write(f"\nIgnored patterns: {', '.join(ignored)}")

        # Show recent commits if requested
        if log_count > 0:
            self.stdout.write(f"\nRecent commits (last {log_count}):")
            commits = services.dolt_log(limit=log_count)
            for commit in commits:
                hash_short = commit["commit_hash"][:8]
                date = commit["date"]
                message = commit["message"].split("\n")[0]  # First line only
                self.stdout.write(f"  {hash_short} {date} - {message}")

    def _format_status(self, status_rows: list[dict[str, Any]]) -> str:
        """Format dolt_status output for display."""
        if not status_rows:
            return "No changes"

        output = []
        for row in status_rows:
            staged = "staged" if row.get("staged", 0) else "modified"
            table = row.get("table_name", "unknown")
            status = row.get("status", "")
            output.append(f"  {staged}: {table} ({status})")
        return "\n".join(output)
