"""Auto-update checker for DualEntry CLI."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import typer

from dualentry_cli import __version__

_CACHE_DIR = Path.home() / ".dualentry"
_UPDATE_CACHE = _CACHE_DIR / ".update_check.json"
_CHECK_INTERVAL = 86400  # 24 hours
_REPO = "git+https://github.com/dualentry/dualentry-cli.git"


def _read_cache() -> dict:
    if not _UPDATE_CACHE.exists():
        return {}
    try:
        return json.loads(_UPDATE_CACHE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_cache(data: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _UPDATE_CACHE.write_text(json.dumps(data))


def _fetch_latest_version() -> str | None:
    """Fetch latest version from GitHub by reading __init__.py from main branch."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--refs", "https://github.com/dualentry/dualentry-cli.git", "refs/tags/v*"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        # Parse tags like "refs/tags/v0.2.0" and pick the latest
        tags = []
        for line in result.stdout.strip().splitlines():
            ref = line.split("refs/tags/")[-1]
            if ref.startswith("v"):
                tags.append(ref[1:])  # strip "v"
        if not tags:
            return None
        tags.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
        return tags[0]
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def check_for_updates() -> None:
    """Check for updates once per day and prompt if a newer version is available."""
    cache = _read_cache()
    last_check = cache.get("last_check", 0)
    now = time.time()

    if now - last_check < _CHECK_INTERVAL:
        return

    latest = _fetch_latest_version()
    _write_cache({"last_check": now, "latest_version": latest})

    if latest and latest != __version__ and _is_newer(latest, __version__):
        typer.secho(
            f"\nUpdate available: {__version__} → {latest}. Run: uv tool upgrade dualentry-cli",
            fg=typer.colors.YELLOW,
            err=True,
        )


def _is_newer(latest: str, current: str) -> bool:
    try:
        latest_parts = [int(x) for x in latest.split(".")]
        current_parts = [int(x) for x in current.split(".")]
    except ValueError:
        return False
    else:
        return latest_parts > current_parts
