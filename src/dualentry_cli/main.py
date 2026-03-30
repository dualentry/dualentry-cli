"""DualEntry CLI entry point."""
import os
import typer
from dualentry_cli.auth import clear_api_key, load_api_key, run_login_flow, store_api_key
from dualentry_cli.config import Config

app = typer.Typer(name="dualentry", help="DualEntry accounting CLI", no_args_is_help=True)
auth_app = typer.Typer(help="Authentication commands")
app.add_typer(auth_app, name="auth")

def version_callback(value: bool):
    if value:
        from dualentry_cli import __version__
        typer.echo(f"dualentry-cli {__version__}")
        raise typer.Exit

@app.callback()
def main(version: bool = typer.Option(False, "--version", "-v", help="Show version and exit.", callback=version_callback, is_eager=True)):
    """DualEntry accounting CLI."""

@auth_app.command()
def login(api_url: str = typer.Option(None, "--api-url", help="API base URL override")):
    """Log in to DualEntry via browser."""
    config = Config()
    url = api_url or config.api_url
    result = run_login_flow(api_url=url)
    store_api_key(result["api_key"])
    config.organization_id = result["organization_id"]
    config.user_email = result["user_email"]
    config.save()
    typer.echo(f"Logged in as {result['user_email']} (org: {result['organization_id']})")

@auth_app.command()
def logout():
    """Log out and clear stored credentials."""
    try:
        clear_api_key()
    except Exception:
        pass
    typer.echo("Logged out.")

@auth_app.command()
def status():
    """Show current authentication status."""
    env_key = os.environ.get("X_API_KEY")
    if env_key:
        typer.echo("Authenticated via X_API_KEY environment variable")
        return
    api_key = load_api_key()
    if not api_key:
        typer.echo("Not logged in. Run: dualentry auth login")
        raise typer.Exit(code=1)
    config = Config()
    typer.echo(f"Logged in as: {config.user_email or 'unknown'}")
    typer.echo(f"Organization: {config.organization_id or 'unknown'}")
    typer.echo(f"API URL: {config.api_url}")

def get_client():
    """Get an authenticated DualEntryClient."""
    from dualentry_cli.client import DualEntryClient
    config = Config()
    env_key = os.environ.get("X_API_KEY")
    if env_key:
        return DualEntryClient(api_url=config.api_url, api_key=env_key)
    api_key = load_api_key()
    if not api_key:
        typer.echo("Not logged in. Run: dualentry auth login")
        raise typer.Exit(code=1)
    return DualEntryClient(api_url=config.api_url, api_key=api_key)

if __name__ == "__main__":
    app()
