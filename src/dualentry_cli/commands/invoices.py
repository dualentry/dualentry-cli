"""Invoice commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, EndDate, Format, Limit, Offset, Search, StartDate, Status, _do_list
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage invoices", no_args_is_help=True, cls=HelpfulGroup)


@app.command("list")
def list_invoices(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    status: str | None = Status,
    start_date: str | None = StartDate,
    end_date: str | None = EndDate,
    output: str = Format,
):
    """List invoices."""
    from dualentry_cli.main import get_client

    client = get_client()
    _do_list(client, "invoices", "invoice", limit, offset, all_pages, output, search=search, status=status, start_date=start_date, end_date=end_date)


@app.command("get")
def get_invoice(
    number: int = typer.Argument(help="Invoice number"),
    output: str = Format,
):
    """Get an invoice by number."""
    from dualentry_cli.main import get_client

    client = get_client()
    data = client.get(f"/invoices/{number}/")
    format_output(data, resource="invoice", fmt=output)


@app.command("create")
def create_invoice(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with invoice data"),
    output: str = Format,
):
    """Create an invoice from a JSON file."""
    from dualentry_cli.main import get_client

    payload = json.loads(file.read_text())
    client = get_client()
    data = client.post("/invoices/", json=payload)
    format_output(data, resource="invoice", fmt=output)
