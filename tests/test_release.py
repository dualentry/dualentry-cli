"""Tests for scripts/release.py changelog handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("release", Path(__file__).resolve().parent.parent / "scripts" / "release.py")
release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(release)

_TODAY = "2026-10-01"


def test_promotes_unreleased_entries():
    content = "# Changelog\n\n## [Unreleased]\n\n- Add export-jobs commands\n\n## [0.1.18] - 2026-09-01\n\n- Old entry\n"
    new, notes = release.promote_unreleased(content, "0.1.19", _TODAY)
    assert new == ("# Changelog\n\n## [Unreleased]\n\n## [0.1.19] - 2026-10-01\n\n- Add export-jobs commands\n\n## [0.1.18] - 2026-09-01\n\n- Old entry\n")
    assert notes == "- Add export-jobs commands"


def test_empty_unreleased_gives_empty_notes():
    content = "# Changelog\n\n## [Unreleased]\n\n## [0.1.18] - 2026-09-01\n\n"
    new, notes = release.promote_unreleased(content, "0.1.19", _TODAY)
    assert new.startswith("# Changelog\n\n## [Unreleased]\n\n## [0.1.19] - 2026-10-01\n\n## [0.1.18]")
    assert notes == ""


def test_adds_unreleased_when_missing():
    content = "# Changelog\n\n## [0.1.18] - 2026-09-01\n\n"
    new, notes = release.promote_unreleased(content, "0.1.19", _TODAY)
    assert new.startswith("# Changelog\n\n## [Unreleased]\n\n## [0.1.19] - 2026-10-01\n\n## [0.1.18]")
    assert notes == ""


def test_existing_version_only_updates_date():
    content = "# Changelog\n\n## [Unreleased]\n\n## [0.1.19] - 2026-09-30\n\n- Entry\n"
    new, notes = release.promote_unreleased(content, "0.1.19", _TODAY)
    assert new == "# Changelog\n\n## [Unreleased]\n\n## [0.1.19] - 2026-10-01\n\n- Entry\n"
    assert notes == "- Entry"
