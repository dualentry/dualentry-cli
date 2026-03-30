"""Authentication for DualEntry CLI - OAuth flow and credential storage."""

from __future__ import annotations

import hashlib
import secrets
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
import keyring
import typer

_SERVICE_NAME = "dualentry-cli"
_KEY_NAME = "api_key"


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = hashlib.sha256(verifier.encode()).hexdigest()
    return verifier, challenge


def store_api_key(api_key: str) -> None:
    keyring.set_password(_SERVICE_NAME, _KEY_NAME, api_key)


def load_api_key() -> str | None:
    return keyring.get_password(_SERVICE_NAME, _KEY_NAME)


def clear_api_key() -> None:
    keyring.delete_password(_SERVICE_NAME, _KEY_NAME)


def start_authorize(api_url: str, redirect_uri: str, code_challenge: str, state: str) -> str:
    response = httpx.post(
        f"{api_url.rstrip('/')}/public/v2/oauth/authorize/",
        json={"redirect_uri": redirect_uri, "code_challenge": code_challenge, "code_challenge_method": "S256", "state": state},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["authorization_url"]


def exchange_token(api_url: str, code: str, code_verifier: str, redirect_uri: str) -> dict:
    response = httpx.post(
        f"{api_url.rstrip('/')}/public/v2/oauth/token/",
        json={"grant_type": "authorization_code", "code": code, "code_verifier": code_verifier, "redirect_uri": redirect_uri},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


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


def run_login_flow(api_url: str) -> dict:
    port = _find_free_port()
    redirect_uri = f"http://localhost:{port}/callback"
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    _CallbackHandler.code = None
    _CallbackHandler.state = None
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    auth_url = start_authorize(api_url=api_url, redirect_uri=redirect_uri, code_challenge=challenge, state=state)
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
    return exchange_token(api_url=api_url, code=_CallbackHandler.code, code_verifier=verifier, redirect_uri=redirect_uri)
