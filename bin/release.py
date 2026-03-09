#!/usr/bin/env python3
"""
Release script for django-dolt
Bumps version, commits, tags, and pushes to git remote

Usage: ./bin/release.py [patch|minor|major]
Default: patch
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def run_command(
    cmd: list[str], capture_output: bool = True, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(cmd, capture_output=capture_output, text=True, check=check)


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = run_command(["git", "branch", "--show-current"])
    return result.stdout.strip()


def is_working_directory_clean() -> bool:
    """Check if the git working directory is clean."""
    result1 = run_command(["git", "diff", "--quiet"], check=False)
    result2 = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    return result1.returncode == 0 and result2.returncode == 0


def get_current_version() -> Optional[str]:
    """Extract current version from src/django_dolt/__init__.py."""
    init_path = Path(__file__).parent.parent / "src" / "django_dolt" / "__init__.py"

    if not init_path.exists():
        return None

    with open(init_path, "r") as f:
        content = f.read()

    match = re.search(r'^__version__ = "([^"]+)"', content, re.MULTILINE)
    return match.group(1) if match else None


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch components."""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")

    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(current_version: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    major, minor, patch = parse_version(current_version)

    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "major":
        return f"{major + 1}.0.0"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def update_version_in_file(new_version: str) -> bool:
    """Update version in src/django_dolt/__init__.py."""
    init_path = Path(__file__).parent.parent / "src" / "django_dolt" / "__init__.py"

    with open(init_path, "r") as f:
        content = f.read()

    new_content = re.sub(
        r'^__version__ = "[^"]+"',
        f'__version__ = "{new_version}"',
        content,
        flags=re.MULTILINE,
    )

    if new_content == content:
        return False

    with open(init_path, "w") as f:
        f.write(new_content)

    return True


def confirm(prompt: str) -> bool:
    """Ask user for confirmation."""
    response = input(prompt + " (y/N) ").strip().lower()
    return response in ("y", "yes")


def main():
    """Main release process."""
    bump_type = sys.argv[1] if len(sys.argv) > 1 else "patch"

    if bump_type not in ("patch", "minor", "major"):
        print(f"{RED}Error: Invalid bump type '{bump_type}'{NC}")
        print("Usage: release.py [patch|minor|major]")
        sys.exit(1)

    if not is_working_directory_clean():
        print(f"{RED}Error: Working directory is not clean{NC}")
        print("Please commit or stash your changes first")
        run_command(["git", "status", "--short"], capture_output=False)
        sys.exit(1)

    current_branch = get_current_branch()
    if current_branch not in ("main", "master"):
        print(
            f"{YELLOW}Warning: Not on main/master branch (current: {current_branch}){NC}"
        )
        if not confirm("Continue anyway?"):
            sys.exit(1)

    current_version = get_current_version()
    if not current_version:
        print(f"{RED}Error: Could not find version in __init__.py{NC}")
        sys.exit(1)

    print(f"Current version: {GREEN}{current_version}{NC}")

    try:
        new_version = bump_version(current_version, bump_type)
    except ValueError as e:
        print(f"{RED}Error: {e}{NC}")
        sys.exit(1)

    print(f"New version: {GREEN}{new_version}{NC}")

    if not update_version_in_file(new_version):
        print(f"{RED}Error: Failed to update version in __init__.py{NC}")
        sys.exit(1)

    run_command(["git", "add", "src/django_dolt/__init__.py"])

    commit_msg = f"Bump version to {new_version}"
    print(f"{YELLOW}Creating commit: {commit_msg}{NC}")
    run_command(["git", "commit", "-m", commit_msg])

    tag = f"v{new_version}"
    print(f"{YELLOW}Creating tag: {tag}{NC}")
    run_command(["git", "tag", "-a", tag, "-m", f"Release version {new_version}"])

    print(f"\n{YELLOW}Ready to push:{NC}")
    print(f"  - Commit: {commit_msg}")
    print(f"  - Tag: {tag}")
    print("  - Remote: origin")
    print(f"  - Branch: {current_branch}")

    if not confirm("\nPush to remote?"):
        print(f"{YELLOW}Push cancelled. Changes committed locally.{NC}")
        print("To push manually, run:")
        print(f"  git push origin {current_branch}")
        print(f"  git push origin {tag}")
        sys.exit(0)

    print(f"{YELLOW}Pushing to origin...{NC}")
    run_command(["git", "push", "origin", current_branch])
    run_command(["git", "push", "origin", tag])

    print(f"{GREEN}Successfully released version {new_version}{NC}")
    print()
    print("Next steps:")
    print("  1. Create release notes on GitHub")
    print("  2. Publish to PyPI: uv build && uv publish")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error: Command failed: {' '.join(e.cmd)}{NC}")
        if e.stderr:
            print(e.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Cancelled by user{NC}")
        sys.exit(130)
