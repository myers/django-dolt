"""
Django management command to pull changes from Dolt remote.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from django_dolt import services


class Command(BaseCommand):
    """Pull changes from Dolt remote repository."""

    help = "Pull changes from Dolt remote repository"

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
            help="Branch to pull (default: current branch)",
        )
        parser.add_argument(
            "--fetch-only",
            action="store_true",
            help="Only fetch, don't merge",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        remote: str = options["remote"]
        branch: str | None = options["branch"]
        fetch_only: bool = options["fetch_only"]

        current_branch = services.dolt_current_branch()
        target_branch = branch or current_branch

        self.stdout.write(f"Current branch: {current_branch}")

        if fetch_only:
            self.stdout.write(f"Fetching from {remote}...")
            try:
                result = services.dolt_fetch(remote)
                self.stdout.write(self.style.SUCCESS(result))
            except services.DoltError as e:
                self.stdout.write(self.style.ERROR(f"Fetch failed: {e}"))
                return
        else:
            self.stdout.write(f"Pulling {target_branch} from {remote}...")
            try:
                result = services.dolt_pull(remote, target_branch)
                self.stdout.write(self.style.SUCCESS(result))
            except services.DoltPullError as e:
                self.stdout.write(self.style.ERROR(f"Pull failed: {e}"))
                return

        # Show diff summary if there were changes
        self.stdout.write("\nChecking for changes...")
        try:
            commits = services.dolt_log(limit=1)
            if commits:
                latest = commits[0]
                self.stdout.write(
                    f"Latest commit: {latest['commit_hash'][:8]} - "
                    f"{latest['message'].split(chr(10))[0]}"
                )
        except Exception:
            pass  # Non-critical, just informational
