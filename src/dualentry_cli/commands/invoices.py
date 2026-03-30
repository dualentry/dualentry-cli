"""Invoice commands."""
from __future__ import annotations
import json
from pathlib import Path
import typer
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage invoices")

@app.command("list")
def list_invoices(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of items"),
    offset: int = typer.Option(0, "--offset", "-o", help="Offset for pagination"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """List invoices."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get("/invoices/", params={"limit": limit, "offset": offset})
    format_output(data, fmt=output)

@app.command("get")
def get_invoice(
    invoice_id: int = typer.Argument(help="Invoice ID"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """Get a single invoice by ID."""
    from dualentry_cli.main import get_client
    client = get_client()
    data = client.get(f"/invoices/{invoice_id}/")
    format_output(data, fmt=output)

@app.command("create")
def create_invoice(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with invoice data"),
    output: str = typer.Option("table", "--output", help="Output format: table or json"),
):
    """Create an invoice from a JSON file."""
    from dualentry_cli.main import get_client
    payload = json.loads(file.read_text())
    client = get_client()
    data = client.post("/invoices/", json=payload)
    format_output(data, fmt=output)
