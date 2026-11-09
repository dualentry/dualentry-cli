"""Tests for scripts/check_artifacts.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS))  # check_artifacts imports check_changelog as a sibling
_SPEC = importlib.util.spec_from_file_location("check_artifacts", _SCRIPTS / "check_artifacts.py")
check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check)

TEMPLATE = (Path(__file__).resolve().parent.parent / ".github" / "pull_request_template.md").read_text()


def test_untouched_template_has_an_empty_section():
    assert check.artifacts_section(TEMPLATE) == ""
    assert not check.has_evidence(check.artifacts_section(TEMPLATE))


def test_missing_heading():
    assert check.artifacts_section("## Summary\n\nDoes a thing.\n") is None


def test_section_stops_at_the_next_heading():
    body = "## Artifacts\n\nsee below\n\n## Merge note\n\n```\n$ dualentry x\n```\n"
    assert check.artifacts_section(body) == "see below"


def test_subheadings_stay_in_the_section():
    body = "## Artifacts\n\n### Before\n\n```\n$ dualentry x\nError\n```\n"
    assert check.has_evidence(check.artifacts_section(body))


@pytest.mark.parametrize(
    "section",
    [
        "```\n$ dualentry invoices list\nShowing 3 of 359\n```",
        "```bash\n$ dualentry webhooks get abc\n```",
        "![webhook received](https://github.com/user-attachments/assets/abc123)",
        '<img width="600" src="https://example.com/shot.png">',
        "https://github.com/user-attachments/assets/0f1e2d3c",
    ],
)
def test_evidence(section):
    assert check.has_evidence(section)


@pytest.mark.parametrize(
    "section",
    [
        "",
        "N/A",
        "Tested locally, works.",
        "```\n```",
        "```\n   \n```",
        "<!-- ```\n$ dualentry x\n``` -->",
    ],
)
def test_not_evidence(section):
    assert not check.has_evidence(check.artifacts_section(f"## Artifacts\n\n{section}\n"))


def test_heading_match_is_case_insensitive():
    assert check.artifacts_section("## artifacts\n\n```\nok\n```\n") == "```\nok\n```"
