"""
Django management command to push Dolt commits to a remote.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_dolt import services


class Command(BaseCommand):
    """Push Dolt commits to a remote repository."""

    help = "Push Dolt commits to a remote repository"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--remote",
            type=str,
            default="origin",
            help="Remote name (default: origin)",
        )
        parser.add_argument(
            "--branch",
            type=str,
            default=None,
            help="Branch to push (default: current branch)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force push (overwrite remote history)",
        )
        parser.add_argument(
            "--user",
            type=str,
            default=None,
            help="Remote username for auth (default: DOLT_REMOTE_USER env)",
        )
        parser.add_argument(
            "--database",
            type=str,
            default=None,
            help="Django database alias to use (default: default connection)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        remote: str = options["remote"]
        branch: str | None = options["branch"]
        force: bool = options["force"]
        user: str | None = options["user"]
        using: str | None = options["database"]

        current_branch = services.dolt_current_branch(using=using)
        target_branch = branch or current_branch

        self.stdout.write(f"Pushing {target_branch} to {remote}...")
        if force:
            self.stdout.write("  Using --force flag")

        try:
            result = services.dolt_push(
                remote, target_branch, force=force, user=user, using=using
            )
            self.stdout.write(self.style.SUCCESS(result))
        except services.DoltPushError as e:
            self.stdout.write(self.style.ERROR(f"Push failed: {e}"))
