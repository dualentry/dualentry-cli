"""Tests for scripts/check_changelog.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("check_changelog", Path(__file__).resolve().parent.parent / "scripts" / "check_changelog.py")
check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check)


def test_unreleased_entries():
    content = "# Changelog\n\n## [Unreleased]\n\n- New thing\n\n## [0.1.18] - 2026-09-01\n\n- Old thing\n"
    assert check.unreleased_entries(content) == {"- New thing"}


def test_unreleased_entries_empty_or_missing():
    assert check.unreleased_entries("# Changelog\n\n## [Unreleased]\n\n## [0.1.18] - 2026-09-01\n\n- Old\n") == set()
    assert check.unreleased_entries("# Changelog\n\n## [0.1.18] - 2026-09-01\n\n- Old\n") == set()


def test_needs_note():
    assert check.needs_note(["src/dualentry_cli/main.py", "README.md"])
    assert not check.needs_note(["README.md", "tests/test_x.py", ".github/workflows/ci.yml"])
