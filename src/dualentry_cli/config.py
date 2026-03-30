"""Configuration management for DualEntry CLI."""

from __future__ import annotations

import tomllib
from pathlib import Path

_DEFAULT_CONFIG_DIR = Path.home() / ".dualentry"
_CONFIG_FILENAME = "config.toml"


class Config:
    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._config_file = self._config_dir / _CONFIG_FILENAME
        self.api_url: str = "https://api.dualentry.com"
        self.output: str = "table"
        self.organization_id: int | None = None
        self.user_email: str | None = None
        self._load()

    def _load(self):
        if not self._config_file.exists():
            return
        with self._config_file.open("rb") as f:
            data = tomllib.load(f)
        default = data.get("default", {})
        self.api_url = default.get("api_url", self.api_url)
        self.output = default.get("output", self.output)
        auth = data.get("auth", {})
        self.organization_id = auth.get("organization_id")
        self.user_email = auth.get("user_email")

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "[default]",
            f'api_url = "{self.api_url}"',
            f'output = "{self.output}"',
            "",
        ]
        if self.organization_id is not None or self.user_email is not None:
            lines.append("[auth]")
            if self.organization_id is not None:
                lines.append(f"organization_id = {self.organization_id}")
            if self.user_email is not None:
                lines.append(f'user_email = "{self.user_email}"')
            lines.append("")
        self._config_file.write_text("\n".join(lines))
