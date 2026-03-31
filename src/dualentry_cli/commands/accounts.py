"""Account commands."""

from __future__ import annotations

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, Format, Limit, Offset, Search, _do_list
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage accounts", no_args_is_help=True, cls=HelpfulGroup)


@app.command("list")
def list_accounts(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    output: str = Format,
):
    """List accounts."""
    from dualentry_cli.main import get_client

    client = get_client()
    _do_list(client, "accounts", "account", limit, offset, all_pages, output, search=search)


@app.command("get")
def get_account(
    account_id: int = typer.Argument(help="Account number"),
    output: str = Format,
):
    """Get an account by number."""
    from dualentry_cli.main import get_client

    client = get_client()
    data = client.get(f"/accounts/{account_id}/")
    format_output(data, resource="account", fmt=output)
