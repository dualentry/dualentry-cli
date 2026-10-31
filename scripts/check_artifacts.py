#!/usr/bin/env python3
"""
Fail when a PR changes the CLI without showing it working against a real API.

Unit tests mock the API client, so they check the CLI against the author's reading
of the API rather than the API itself. The Artifacts section is where the author
shows real runs: command output, JSON responses, screenshots of the result in the app.

Usage:
    PR_BODY="..." python scripts/check_artifacts.py <base-ref>   # e.g. origin/main
"""

from __future__ import annotations

import os
import re
import sys

from check_changelog import git, needs_note

HEADING = re.compile(r"^##\s+Artifacts\s*$", re.MULTILINE | re.IGNORECASE)
NEXT_HEADING = re.compile(r"^#{1,2}\s", re.MULTILINE)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Evidence is captured output in a fenced block, or an uploaded image or video.
FENCED_BLOCK = re.compile(r"^```.*?\n.*?\S.*?^```", re.MULTILINE | re.DOTALL)
UPLOAD = re.compile(r"!\[[^\]]*\]\([^)]+\)|<img\s|<video\s|https://github\.com/user-attachments/\S+", re.IGNORECASE)


def artifacts_section(body: str) -> str | None:
    """The Artifacts section's text without template comments, or None when there isn't one."""
    match = HEADING.search(body)
    if match is None:
        return None
    rest = body[match.end() :]
    end = NEXT_HEADING.search(rest)
    return COMMENT.sub("", rest[: end.start()] if end else rest).strip()


def has_evidence(section: str) -> bool:
    return bool(FENCED_BLOCK.search(section) or UPLOAD.search(section))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    base = git("merge-base", sys.argv[1], "HEAD").strip()

    if not needs_note(git("diff", "--name-only", base, "HEAD").splitlines()):
        print("No user-facing changes; artifacts not required.")
        return 0

    section = artifacts_section(os.environ.get("PR_BODY") or "")
    if section is None:
        print("This PR changes src/ but its description has no `## Artifacts` section.")
    elif not has_evidence(section):
        print("The `## Artifacts` section has no evidence: add command output in a ``` block, or a screenshot.")
    else:
        print("Artifacts found.")
        return 0

    print(
        "Show the change working against a real API: the commands you ran and their output, "
        "the JSON response, or a screenshot of the result in the app. Redact secrets first; "
        "this repository is public. Apply the `skip-artifacts` label for changes with nothing to run.",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
