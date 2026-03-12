"""
Release script for django-dolt
Bumps version, commits, tags, and pushes to git remote

Usage:
    bin/release [patch|minor|major]   # Bump version, commit, tag, and push
    bin/release --publish             # Tag and push the current version as-is
Default: patch
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ANSI color codes
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def run_command(
    cmd: list[str], capture_output: bool = True, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a shell command and return the result."""
    return subprocess.run(cmd, capture_output=capture_output, text=True, check=check)


def get_current_branch() -> str:
    """Get the current git branch name."""
    result = run_command(["git", "branch", "--show-current"])
    return str(result.stdout.strip())


def is_working_directory_clean() -> bool:
    """Check if the git working directory is clean."""
    result1 = run_command(["git", "diff", "--quiet"], check=False)
    result2 = run_command(["git", "diff", "--cached", "--quiet"], check=False)
    return result1.returncode == 0 and result2.returncode == 0


def _find_init_path() -> Path:
    """Find the __init__.py file relative to the project root."""
    # Walk up from this file to find the project root (where pyproject.toml is)
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "src" / "django_dolt" / "__init__.py"
    raise FileNotFoundError("Could not find project root (no pyproject.toml)")


def get_current_version() -> str | None:
    """Extract current version from src/django_dolt/__init__.py."""
    init_path = _find_init_path()

    if not init_path.exists():
        return None

    with open(init_path) as f:
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
    init_path = _find_init_path()

    with open(init_path) as f:
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


def tag_and_push(version: str, branch: str) -> None:
    """Tag the current commit and push to origin."""
    tag = f"v{version}"

    # Check if tag already exists
    result = run_command(["git", "tag", "-l", tag])
    if result.stdout.strip():
        print(f"{RED}Error: Tag {tag} already exists{NC}")
        sys.exit(1)

    print(f"{YELLOW}Creating tag: {tag}{NC}")
    run_command(["git", "tag", "-a", tag, "-m", f"Release version {version}"])

    print(f"{YELLOW}Pushing to origin...{NC}")
    run_command(["git", "push", "origin", branch])
    run_command(["git", "push", "origin", tag])

    print(f"\n{GREEN}Successfully released version {version}{NC}")


def main() -> None:
    """Main release process."""
    parser = argparse.ArgumentParser(description="Release django-dolt")
    parser.add_argument(
        "bump_type",
        nargs="?",
        default="patch",
        choices=["patch", "minor", "major"],
        help="Version bump type (default: patch)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Tag and push the current version without bumping",
    )
    args = parser.parse_args()

    if not is_working_directory_clean():
        print(f"{RED}Error: Working directory is not clean{NC}")
        print("Please commit or stash your changes first")
        run_command(["git", "status", "--short"], capture_output=False)
        sys.exit(1)

    current_branch = get_current_branch()
    if current_branch not in ("main", "master"):
        print(
            f"{YELLOW}Warning: Not on main/master branch "
            f"(current: {current_branch}){NC}"
        )
        if not confirm("Continue anyway?"):
            sys.exit(1)

    current_version = get_current_version()
    if not current_version:
        print(f"{RED}Error: Could not find version in __init__.py{NC}")
        sys.exit(1)

    if args.publish:
        print(f"Publishing current version: {GREEN}{current_version}{NC}")
        tag_and_push(current_version, current_branch)
        return

    print(f"Current version: {GREEN}{current_version}{NC}")

    try:
        new_version = bump_version(current_version, args.bump_type)
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

    tag_and_push(new_version, current_branch)


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
