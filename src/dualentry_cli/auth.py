"""Authentication for DualEntry CLI - OAuth 2.1 with PKCE via public API endpoints."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import keyring
import typer

_SERVICE_NAME = "dualentry-cli"
_KEY_NAME_API_KEY = "api_key"

_TOKEN_FILE = Path.home() / ".dualentry" / "tokens.json"


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge per RFC 7636."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# -- Credential storage ------------------------------------------------


def store_api_key(api_key: str) -> None:
    """Store API key. Uses keyring with file fallback."""
    try:
        keyring.set_password(_SERVICE_NAME, _KEY_NAME_API_KEY, api_key)
    except Exception:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"api_key": api_key}))
        _TOKEN_FILE.chmod(0o600)


def load_api_key() -> str | None:
    """Load stored API key."""
    try:
        key = keyring.get_password(_SERVICE_NAME, _KEY_NAME_API_KEY)
        if key:
            return key
    except Exception:
        pass
    if _TOKEN_FILE.exists():
        try:
            data = json.loads(_TOKEN_FILE.read_text())
            return data.get("api_key")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def clear_credentials() -> None:
    """Clear all stored credentials."""
    try:
        keyring.delete_password(_SERVICE_NAME, _KEY_NAME_API_KEY)
    except Exception:
        pass
    if _TOKEN_FILE.exists():
        try:
            _TOKEN_FILE.unlink()
        except OSError:
            pass


# -- OAuth endpoints ---------------------------------------------------


def _authorize(api_url: str, redirect_uri: str, code_challenge: str, state: str) -> str:
    """POST /public/v2/oauth/authorize/ — returns the WorkOS authorization URL."""
    response = httpx.post(
        f"{api_url.rstrip('/')}/public/v2/oauth/authorize/",
        json={
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        },
        timeout=30.0,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        typer.echo(f"Authorization failed (HTTP {exc.response.status_code}): {detail}", err=True)
        raise typer.Exit(code=1) from None
    return response.json()["authorization_url"]


def _exchange_code(api_url: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    """POST /public/v2/oauth/token/ — exchange auth code for API key."""
    response = httpx.post(
        f"{api_url.rstrip('/')}/public/v2/oauth/token/",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        },
        timeout=30.0,
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        typer.echo(f"Token exchange failed (HTTP {exc.response.status_code}): {detail}", err=True)
        raise typer.Exit(code=1) from None
    return response.json()


# -- Local callback server ---------------------------------------------


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None
    state: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = parse_qs(parsed.query)
        _CallbackHandler.code = params.get("code", [None])[0]
        _CallbackHandler.state = params.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Login successful!</h1><p>You can close this window and return to the terminal.</p></body></html>")

    def log_message(self, format, *args):
        pass


# -- Main login flow ---------------------------------------------------


def run_login_flow(api_url: str) -> dict:
    """
    Run the full OAuth login flow via /public/v2/oauth/ endpoints.

    Returns dict with api_key, organization_id, user_email.
    """
    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"
    verifier, challenge = _generate_pkce_pair()
    state = secrets.token_urlsafe(16)

    # Get authorization URL from backend
    auth_url = _authorize(api_url, redirect_uri, challenge, state)

    # Start local server and open browser
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)

    typer.echo("Opening browser for login...")
    typer.echo(f"If the browser doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    try:
        server.handle_request()
    except KeyboardInterrupt:
        server.server_close()
        typer.echo("\nLogin cancelled.")
        raise typer.Exit(code=1) from None
    server.server_close()

    if not _CallbackHandler.code:
        typer.echo("No authorization code received.")
        raise typer.Exit(code=1)
    if _CallbackHandler.state != state:
        typer.echo("State mismatch - possible CSRF attack.")
        raise typer.Exit(code=1)

    # Exchange code for API key
    token_response = _exchange_code(api_url, _CallbackHandler.code, verifier, redirect_uri)

    return {
        "api_key": token_response["api_key"],
        "organization_id": token_response["organization_id"],
        "user_email": token_response["user_email"],
    }
