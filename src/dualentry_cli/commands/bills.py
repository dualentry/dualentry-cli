"""Bill commands."""
from __future__ import annotations
import json
from pathlib import Path
import typer
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage bills")

@app.command("list")
def list_bills(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """List bills."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get("/bills/", params={"limit": limit, "offset": offset})
    format_output(data, fmt=output)

@app.command("get")
def get_bill(
    bill_id: int = typer.Argument(help="Bill ID"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """Get a single bill by ID."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get(f"/bills/{bill_id}/")
    format_output(data, fmt=output)

@app.command("create")
def create_bill(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with bill data"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """Create a bill from a JSON file."""
    from dualentry_cli.main import get_client
    payload = json.loads(file.read_text())
    client = get_client()
    data = client.post("/bills/", json=payload)
    format_output(data, fmt=output)
