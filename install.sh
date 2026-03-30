#!/usr/bin/env bash
set -euo pipefail

# DualEntry CLI installer
# Usage: curl -sSL <raw-url>/install.sh | bash

REPO="git+ssh://git@github.com/dualentry/dualentry-cli.git"
TOOL_NAME="dualentry-cli"

echo "Installing DualEntry CLI..."

# Prefer uv, fall back to pipx
if command -v uv &>/dev/null; then
    echo "Using uv..."
    uv tool install "$REPO"
elif command -v pipx &>/dev/null; then
    echo "Using pipx..."
    pipx install "$REPO"
else
    echo "Error: requires uv or pipx"
    echo ""
    echo "Install uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Install pipx: brew install pipx && pipx ensurepath"
    exit 1
fi

echo ""
echo "Installed! Run: dualentry auth login"
