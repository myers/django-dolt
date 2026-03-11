"""
Django management command to sync Dolt database - commit and push changes.
"""

from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_dolt import services


class Command(BaseCommand):
    """Sync Dolt database - commit and push changes to remote."""

    help = "Sync Dolt database - commit and push changes to remote"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "message",
            nargs="?",
            type=str,
            default=None,
            help="Optional commit message. If not provided, a timestamp will be used.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force push to remote (overwrite remote history)",
        )
        parser.add_argument(
            "--no-push",
            action="store_true",
            help="Commit changes but don't push to remote",
        )
        parser.add_argument(
            "--author",
            type=str,
            default="Django <django@localhost>",
            help="Author string in 'Name <email>' format",
        )
        parser.add_argument(
            "--tables",
            type=str,
            nargs="*",
            help="Specific tables to stage (default: all with changes)",
        )
        parser.add_argument(
            "--database",
            type=str,
            default=None,
            help="Django database alias to use (default: default connection)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        message: str | None = options["message"]
        force: bool = options["force"]
        no_push: bool = options["no_push"]
        author: str = options["author"]
        tables: list[str] | None = options.get("tables")
        using: str | None = options["database"]

        self.stdout.write("Checking for uncommitted changes...")

        status = services.dolt_status(exclude_ignored=True, using=using)

        if not status:
            self.stdout.write("No changes to commit")

            if not no_push:
                self._try_push(force, using)
            return

        self.stdout.write("Found changes to commit:")
        self.stdout.write(services.format_status_rows(status))

        self.stdout.write("\nCommitting changes...")
        if message:
            self.stdout.write(f"   Message: {message}")

        # Create commit message if not provided
        if message is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"Database update at {timestamp}"

        if tables:
            # Explicit tables: stage each one, then commit
            for table in tables:
                try:
                    services.dolt_add(table, using=using)
                    self.stdout.write(f"  Staged: {table}")
                except services.DoltError as e:
                    self.stdout.write(f"  Note: Could not stage {table}: {e}")

            try:
                commit_hash = services.dolt_commit(message, author=author, using=using)
            except services.DoltCommitError as e:
                self.stdout.write(self.style.ERROR(f"Commit failed: {e}"))
                return
        else:
            # No explicit tables: atomic stage-all + commit
            try:
                commit_hash = services.dolt_add_and_commit(
                    message, author=author, using=using
                )
            except services.DoltCommitError as e:
                self.stdout.write(self.style.ERROR(f"Commit failed: {e}"))
                return

        if commit_hash:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Committed: {message} (commit: {commit_hash[:8]})"
                )
            )
        else:
            self.stdout.write("No changes to commit after staging")
            return

        if not no_push:
            self._try_push(force, using)

    def _try_push(self, force: bool, using: str | None) -> None:
        """Attempt to push to remote."""
        self.stdout.write("\nPushing to remote...")
        if force:
            self.stdout.write("   Using --force flag")

        try:
            result = services.dolt_push(force=force, using=using)
            self.stdout.write(self.style.SUCCESS(f"Success: {result}"))
        except services.DoltPushError as e:
            self.stdout.write(self.style.ERROR(f"Push failed: {e}"))
