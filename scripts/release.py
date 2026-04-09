#!/usr/bin/env python3
"""
Release script for DualEntry CLI.

Usage:
    python scripts/release.py patch   # 0.1.0 -> 0.1.1
    python scripts/release.py minor   # 0.1.0 -> 0.2.0
    python scripts/release.py major   # 0.1.0 -> 1.0.0
    python scripts/release.py 0.2.0   # Explicit version

This script:
1. Bumps version in pyproject.toml and __init__.py
2. Updates CHANGELOG.md with today's date
3. Commits the changes
4. Creates a git tag
5. Pushes to GitHub
6. Creates a GitHub release (triggers CI to build binaries)
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT_FILE = ROOT / "src" / "dualentry_cli" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def get_current_version() -> str:
    """Read current version from __init__.py."""
    content = INIT_FILE.read_text()
    match = re.search(r'__version__ = "([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in __init__.py")
    return match.group(1)


def bump_version(current: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    if bump_type in ("patch", "minor", "major"):
        parts = [int(p) for p in current.split(".")]
        while len(parts) < 3:
            parts.append(0)

        if bump_type == "patch":
            parts[2] += 1
        elif bump_type == "minor":
            parts[1] += 1
            parts[2] = 0
        elif bump_type == "major":
            parts[0] += 1
            parts[1] = 0
            parts[2] = 0

        return ".".join(str(p) for p in parts)
    # Explicit version
    if not re.match(r"^\d+\.\d+\.\d+$", bump_type):
        raise ValueError(f"Invalid version format: {bump_type}")
    return bump_type


def update_pyproject(new_version: str) -> None:
    """Update version in pyproject.toml."""
    content = PYPROJECT.read_text()
    content = re.sub(r'^version = "[^"]+"', f'version = "{new_version}"', content, flags=re.MULTILINE)
    PYPROJECT.write_text(content)


def update_init(new_version: str) -> None:
    """Update version in __init__.py."""
    content = INIT_FILE.read_text()
    content = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content)
    INIT_FILE.write_text(content)


def update_changelog(new_version: str) -> None:
    """Add new version entry to CHANGELOG.md if not already present."""
    content = CHANGELOG.read_text()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    new_entry = f"## [{new_version}] - {today}\n\n"

    # Check if this version is already in the changelog
    if f"## [{new_version}]" in content:
        # Just update the date
        content = re.sub(
            rf"## \[{re.escape(new_version)}\] - \d{{4}}-\d{{2}}-\d{{2}}",
            f"## [{new_version}] - {today}",
            content,
        )
    else:
        # Add new entry after "# Changelog"
        content = content.replace("# Changelog\n", f"# Changelog\n\n{new_entry}")

    CHANGELOG.write_text(content)


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, check=check, capture_output=True, text=True)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    bump_type = sys.argv[1]
    current = get_current_version()
    new_version = bump_version(current, bump_type)

    print(f"\n  Releasing {current} -> {new_version}\n")

    # Check if tag already exists
    result = run(["git", "tag", "-l", f"v{new_version}"], check=False)
    if result.stdout.strip():
        print(f"  ERROR: Tag v{new_version} already exists.")
        print("  Either the version files are out of sync, or you need a different bump type.")
        return 1

    # Check for uncommitted changes
    result = run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        print("  ERROR: Uncommitted changes detected. Commit or stash them first.")
        return 1

    # Check we're on main branch
    result = run(["git", "branch", "--show-current"])
    if result.stdout.strip() != "main":
        print(f"  WARNING: Not on main branch (on {result.stdout.strip()})")
        response = input("  Continue anyway? [y/N] ")
        if response.lower() != "y":
            return 1

    # Run tests
    print("\n  Running tests...")
    result = run(["uv", "run", "pytest", "tests/", "-q"], check=False)
    if result.returncode != 0:
        print("  ERROR: Tests failed")
        print(result.stdout)
        print(result.stderr)
        return 1
    print("  Tests passed!")

    # Run linter
    print("\n  Running linter...")
    result = run(["uv", "run", "ruff", "check", "."], check=False)
    if result.returncode != 0:
        print("  ERROR: Linter failed")
        print(result.stdout)
        return 1
    print("  Linter passed!")

    # Update versions
    print("\n  Updating version files...")
    update_pyproject(new_version)
    update_init(new_version)
    update_changelog(new_version)

    # Commit
    print("\n  Committing changes...")
    run(["git", "add", "pyproject.toml", "src/dualentry_cli/__init__.py", "CHANGELOG.md"])
    run(["git", "commit", "-m", f"chore: release v{new_version}"])

    # Tag
    print("\n  Creating tag...")
    run(["git", "tag", f"v{new_version}"])

    # Push
    print("\n  Pushing to GitHub...")
    run(["git", "push", "origin", "main"])
    run(["git", "push", "origin", f"v{new_version}"])

    # Create GitHub release
    print("\n  Creating GitHub release...")
    result = run(
        ["gh", "release", "create", f"v{new_version}", "--title", f"v{new_version}", "--generate-notes"],
        check=False,
    )
    if result.returncode != 0:
        print(f"  WARNING: Could not create GitHub release: {result.stderr}")
        print("  Create it manually at: https://github.com/dualentry/dualentry-cli/releases/new")
    else:
        print(f"  Release created: https://github.com/dualentry/dualentry-cli/releases/tag/v{new_version}")

    print(f"\n  Done! Released v{new_version}")
    print("  CI will build binaries and update Homebrew tap automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
