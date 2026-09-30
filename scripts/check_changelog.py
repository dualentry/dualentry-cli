#!/usr/bin/env python3
"""
Fail when a PR changes the CLI without adding a CHANGELOG.md Unreleased entry.

Usage:
    python scripts/check_changelog.py <base-ref>   # e.g. origin/main
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

UNRELEASED = "## [Unreleased]"
CHANGELOG = Path("CHANGELOG.md")
# Changes under these paths ship to users and need a release note.
USER_FACING = ("src/",)


def unreleased_entries(changelog: str) -> set[str]:
    """Non-empty lines of the Unreleased section."""
    if UNRELEASED not in changelog:
        return set()
    section = changelog.split(UNRELEASED, 1)[1].split("\n## [", 1)[0]
    return {line.strip() for line in section.splitlines() if line.strip()}


def needs_note(changed_files: list[str]) -> bool:
    return any(path.startswith(USER_FACING) for path in changed_files)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = git("merge-base", sys.argv[1], "HEAD").strip()

    changed = git("diff", "--name-only", base, "HEAD").splitlines()
    if not needs_note(changed):
        print("No user-facing changes; release note not required.")
        return 0

    head_entries = unreleased_entries(CHANGELOG.read_text())
    base_entries = unreleased_entries(git("show", f"{base}:{CHANGELOG}"))
    if head_entries - base_entries:
        print("Release note found.")
        return 0

    print(
        f"This PR changes {', '.join(USER_FACING)} but adds no entry under `{UNRELEASED}` in {CHANGELOG}.\n"
        "Add a bullet describing the change, or apply the `skip-changelog` label if it isn't user-facing.",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
