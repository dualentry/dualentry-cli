"""Authentication for DualEntry CLI - OAuth flow via MCP endpoints and credential storage."""

from __future__ import annotations

import hashlib
import json
import secrets
import socket
import webbrowser
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import keyring
import typer


class CodeChallengeMethod(StrEnum):
    S256 = "S256"


class GrantType(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    REFRESH_TOKEN = "refresh_token"  # noqa: S105


class ResponseType(StrEnum):
    CODE = "code"


class TokenEndpointAuthMethod(StrEnum):
    NONE = "none"


_SERVICE_NAME = "dualentry-cli"
_KEY_NAME_ACCESS = "access_token"
_KEY_NAME_REFRESH = "refresh_token"
_KEY_NAME_API_KEY = "api_key"  # legacy, still checked for migration

_TOKEN_FILE = Path.home() / ".dualentry" / "tokens.json"


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    return verifier, challenge


# ── Token storage ────────────────────────────────────────────────────


def store_tokens(access_token: str, refresh_token: str) -> None:
    """Store OAuth tokens. Uses keyring with file fallback."""
    try:
        keyring.set_password(_SERVICE_NAME, _KEY_NAME_ACCESS, access_token)
        keyring.set_password(_SERVICE_NAME, _KEY_NAME_REFRESH, refresh_token)
    except Exception:
        # Fallback to file storage (e.g. CI, headless)
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"access_token": access_token, "refresh_token": refresh_token}))
        _TOKEN_FILE.chmod(0o600)


def load_tokens() -> tuple[str | None, str | None]:
    """Load OAuth tokens. Returns (access_token, refresh_token)."""
    try:
        access = keyring.get_password(_SERVICE_NAME, _KEY_NAME_ACCESS)
        refresh = keyring.get_password(_SERVICE_NAME, _KEY_NAME_REFRESH)
        if access and refresh:
            return access, refresh
    except Exception:
        pass
    # File fallback
    if _TOKEN_FILE.exists():
        try:
            data = json.loads(_TOKEN_FILE.read_text())
            return data.get("access_token"), data.get("refresh_token")
        except (json.JSONDecodeError, OSError):
            pass
    return None, None


def load_api_key() -> str | None:
    """Load legacy API key (for X_API_KEY env var compat check)."""
    try:
        return keyring.get_password(_SERVICE_NAME, _KEY_NAME_API_KEY)
    except Exception:
        return None


def clear_credentials() -> None:
    """Clear all stored credentials."""
    for key in (_KEY_NAME_ACCESS, _KEY_NAME_REFRESH, _KEY_NAME_API_KEY):
        try:
            keyring.delete_password(_SERVICE_NAME, key)
        except Exception:
            pass
    if _TOKEN_FILE.exists():
        try:
            _TOKEN_FILE.unlink()
        except OSError:
            pass


# legacy alias
clear_api_key = clear_credentials


# ── MCP OAuth client registration ───────────────────────────────────


def _register_client(mcp_url: str, redirect_uri: str) -> dict:
    """Register as an OAuth client with the MCP server (dynamic client registration)."""
    response = httpx.post(
        f"{mcp_url}/register",
        json={
            "client_name": "DualEntry CLI",
            "redirect_uris": [redirect_uri],
            "grant_types": [GrantType.AUTHORIZATION_CODE, GrantType.REFRESH_TOKEN],
            "response_types": [ResponseType.CODE],
            "token_endpoint_auth_method": TokenEndpointAuthMethod.NONE,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


# ── OAuth flow ───────────────────────────────────────────────────────


def _start_authorize(mcp_url: str, client_id: str, redirect_uri: str, code_challenge: str, state: str) -> str:
    """Build the authorization URL and return it (the MCP /authorize endpoint redirects to WorkOS)."""
    params = {
        "response_type": ResponseType.CODE,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": CodeChallengeMethod.S256,
        "state": state,
    }
    return f"{mcp_url}/authorize?{urlencode(params)}"


def _exchange_token(mcp_url: str, client_id: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    """Exchange authorization code for access/refresh tokens at MCP /token endpoint."""
    response = httpx.post(
        f"{mcp_url}/token",
        data={
            "grant_type": GrantType.AUTHORIZATION_CODE,
            "client_id": client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(mcp_url: str, client_id: str, refresh_token: str) -> dict:
    """Use refresh token to get a new access/refresh token pair."""
    response = httpx.post(
        f"{mcp_url}/token",
        data={
            "grant_type": GrantType.REFRESH_TOKEN,
            "client_id": client_id,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


# ── Local callback server ────────────────────────────────────────────


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _CallbackHandler.code = params.get("code", [None])[0]
        _CallbackHandler.state = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Login successful!</h1><p>You can close this window and return to the terminal.</p></body></html>")

    def log_message(self, format, *args):
        pass


# ── Main login flow ──────────────────────────────────────────────────


def run_login_flow(api_url: str) -> dict:
    """
    Run the full OAuth login flow using MCP endpoints.

    Returns dict with access_token, refresh_token, and token metadata.
    """
    mcp_url = f"{api_url.rstrip('/')}/mcp"

    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    # Register as OAuth client
    client_info = _register_client(mcp_url, redirect_uri)
    client_id = client_info["client_id"]

    # Build authorize URL
    auth_url = _start_authorize(mcp_url, client_id, redirect_uri, challenge, state)

    # Start local server and open browser
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)

    typer.echo("Opening browser for login...")
    typer.echo(f"If the browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    server.handle_request()
    server.server_close()

    if not _CallbackHandler.code:
        typer.echo("No authorization code received.")
        raise typer.Exit(code=1)
    if _CallbackHandler.state != state:
        typer.echo("State mismatch - possible CSRF attack.")
        raise typer.Exit(code=1)

    # Exchange code for tokens
    token_response = _exchange_token(mcp_url, client_id, _CallbackHandler.code, verifier, redirect_uri)

    return {
        "access_token": token_response["access_token"],
        "refresh_token": token_response.get("refresh_token", ""),
        "expires_in": token_response.get("expires_in"),
        "client_id": client_id,
    }
