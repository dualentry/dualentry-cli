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
        self.wfile.write(b"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DualEntry - Login Successful</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #f8fafc;
        }
        .container {
            text-align: center;
            padding: 3rem;
            max-width: 420px;
        }
        .logo {
            font-size: 2.5rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 2rem;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .checkmark {
            width: 80px;
            height: 80px;
            margin: 0 auto 1.5rem;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: scale-in 0.3s ease-out;
        }
        .checkmark svg { width: 40px; height: 40px; stroke: white; }
        @keyframes scale-in {
            0% { transform: scale(0); opacity: 0; }
            100% { transform: scale(1); opacity: 1; }
        }
        h1 {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            color: #f1f5f9;
        }
        p {
            color: #94a3b8;
            font-size: 0.95rem;
            line-height: 1.6;
        }
        .hint {
            margin-top: 2rem;
            padding: 1rem;
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 8px;
            font-size: 0.85rem;
            color: #93c5fd;
        }
        code {
            background: rgba(0, 0, 0, 0.3);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">DualEntry</div>
        <div class="checkmark">
            <svg fill="none" viewBox="0 0 24 24" stroke-width="3" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
        </div>
        <h1>Authentication Successful</h1>
        <p>You're all set. You can close this window and return to your terminal.</p>
        <div class="hint">Your CLI is now ready. Try <code>dualentry auth status</code> to verify.</div>
    </div>
</body>
</html>""")

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
