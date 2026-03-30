"""Account commands."""
from __future__ import annotations
import typer
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage accounts")

@app.command("list")
def list_accounts(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """List accounts."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get("/accounts/", params={"limit": limit, "offset": offset})
    format_output(data, fmt=output)

@app.command("get")
def get_account(
    account_id: int = typer.Argument(help="Account ID"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """Get a single account by ID."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get(f"/accounts/{account_id}/")
    format_output(data, fmt=output)
