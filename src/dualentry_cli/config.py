"""Configuration management for DualEntry CLI."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

_DEFAULT_CONFIG_DIR = Path.home() / ".dualentry"
_CONFIG_FILENAME = "config.toml"

ENVIRONMENTS = {
    "prod": "https://api.dualentry.com",
    "dev": "https://api-dev.dualentry.com",
}


class Config:
    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or _DEFAULT_CONFIG_DIR
        self._config_file = self._config_dir / _CONFIG_FILENAME
        self.api_url: str = ENVIRONMENTS["prod"]
        self.output: str = "table"
        self.organization_id: int | None = None
        self.user_email: str | None = None
        self._load()
        # Env var overrides config file
        env_url = os.environ.get("DUALENTRY_API_URL")
        if env_url:
            self.api_url = env_url

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

    @property
    def env_name(self) -> str:
        """Return the environment name based on the current api_url."""
        for name, url in ENVIRONMENTS.items():
            if self.api_url == url:
                return name
        return "custom"

    @staticmethod
    def _escape_toml_string(value: str) -> str:
        """Escape a value for safe inclusion in a TOML double-quoted string."""
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "[default]",
            f'api_url = "{self._escape_toml_string(self.api_url)}"',
            f'output = "{self._escape_toml_string(self.output)}"',
            "",
        ]
        has_auth = any(v is not None for v in (self.organization_id, self.user_email))
        if has_auth:
            lines.append("[auth]")
            if self.organization_id is not None:
                lines.append(f"organization_id = {self.organization_id}")
            if self.user_email is not None:
                lines.append(f'user_email = "{self._escape_toml_string(self.user_email)}"')
            lines.append("")
        self._config_file.write_text("\n".join(lines))
