#!/bin/sh
set -e

REPO="dualentry/dualentry-cli"
INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

get_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo "x86_64" ;;
    arm64|aarch64) echo "arm64" ;;
    *) echo "Unsupported architecture: $(uname -m)" >&2; exit 1 ;;
  esac
}

get_os() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux) echo "linux" ;;
    *) echo "Unsupported OS: $(uname -s)" >&2; exit 1 ;;
  esac
}

OS=$(get_os)
ARCH=$(get_arch)
TARGET="${OS}-${ARCH}"

if [ "$OS" = "linux" ] && [ "$ARCH" = "arm64" ]; then
  echo "Linux arm64 is not currently supported." >&2
  exit 1
fi

echo "Detecting latest release..."
LATEST=$(curl -s "https://api.github.com/repos/${REPO}/releases/latest" | grep '"tag_name"' | sed 's/.*: "//;s/".*//')

if [ -z "$LATEST" ]; then
  echo "Failed to detect latest release." >&2
  exit 1
fi

URL="https://github.com/${REPO}/releases/download/${LATEST}/dualentry-${TARGET}"
TMPFILE=$(mktemp)

echo "Downloading dualentry ${LATEST} for ${TARGET}..."
curl -fSL "$URL" -o "$TMPFILE"

chmod +x "$TMPFILE"
mkdir -p "$INSTALL_DIR"

if [ -w "$INSTALL_DIR" ]; then
  mv "$TMPFILE" "$INSTALL_DIR/dualentry"
else
  echo "Installing to ${INSTALL_DIR} (requires sudo)..."
  sudo mv "$TMPFILE" "$INSTALL_DIR/dualentry"
fi

echo "Installed dualentry to ${INSTALL_DIR}/dualentry"
echo "Run 'dualentry --help' to get started."
