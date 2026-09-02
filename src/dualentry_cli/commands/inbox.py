"""
Inbox commands.

The inbox splits into two sub-resources with their own list and detail routes.
Both detail routes take a required type discriminator (`transaction_type` /
`record_type`) as a query parameter, which the generic resource factory has no
way to send, so these commands are wired up by hand.
"""

from __future__ import annotations

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, EndDate, Format, Limit, Offset, Search, StartDate, _do_list
from dualentry_cli.output import format_output

transactions_app = typer.Typer(help="Manage transactions awaiting approval", no_args_is_help=True, cls=HelpfulGroup)
records_app = typer.Typer(help="Manage non-monetary records awaiting approval", no_args_is_help=True, cls=HelpfulGroup)


def _many(values: list | None) -> list | None:
    """Return a repeatable option's values, or None when it was not passed."""
    return list(values) if values else None


def _show_detail(data: dict, resource: str, output: str) -> None:
    """Print a detail record; say so plainly when the record is not in the inbox."""
    # The API answers with an empty object rather than a 404 when a record has
    # no approval workflow attached, which prints as an empty table otherwise.
    if not data and output != "json":
        typer.echo("This record is not in the inbox.")
        return
    format_output(data, resource=resource, fmt=output)


@transactions_app.command("list")
def list_transactions(
    *,
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    transaction_type: list[str] | None = typer.Option(None, "--transaction-type", help="Filter by transaction type (repeatable)"),
    status: list[str] | None = typer.Option(None, "--status", help="Filter by approval status (repeatable)"),
    company: list[int] | None = typer.Option(None, "--company", "-c", help="Filter by company ID (repeatable)"),
    customer: list[int] | None = typer.Option(None, "--customer", help="Filter by customer ID (repeatable)"),
    start_date: str | None = StartDate,
    end_date: str | None = EndDate,
    min_amount: str | None = typer.Option(None, "--min-amount", help="Only transactions at or above this amount"),
    max_amount: str | None = typer.Option(None, "--max-amount", help="Only transactions at or below this amount"),
    output: str = Format,
):
    """List transactions awaiting approval."""
    from dualentry_cli.main import get_client

    client = get_client()
    _do_list(
        client,
        "inbox/transactions",
        "inbox-transaction",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        search=search,
        status=_many(status),
        start_date=start_date,
        end_date=end_date,
        status_param="approval_status",
        transaction_type=_many(transaction_type),
        company_id=_many(company),
        customer_id=_many(customer),
        min_amount=min_amount,
        max_amount=max_amount,
    )


@transactions_app.command("get")
def get_transaction(
    record_id: int = typer.Argument(help="Record ID of the transaction"),
    transaction_type: str = typer.Option(..., "--transaction-type", help="Transaction type of that record, e.g. invoice"),
    output: str = Format,
):
    """Get the approval details of one transaction."""
    from dualentry_cli.main import get_client

    client = get_client()
    data = client.get(f"/inbox/transactions/{record_id}/", params={"transaction_type": transaction_type})
    _show_detail(data, "inbox-transaction", output)


@records_app.command("list")
def list_records(
    *,
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    record_type: list[str] | None = typer.Option(None, "--record-type", help="Filter by record type (repeatable)"),
    status: list[str] | None = typer.Option(None, "--status", help="Filter by approval status (repeatable)"),
    output: str = Format,
):
    """List non-monetary records awaiting approval."""
    from dualentry_cli.main import get_client

    client = get_client()
    _do_list(
        client,
        "inbox/records",
        "inbox-record",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        search=search,
        status=_many(status),
        status_param="approval_status",
        record_type=_many(record_type),
    )


@records_app.command("get")
def get_record(
    record_id: int = typer.Argument(help="Record ID of the customer or vendor"),
    record_type: str = typer.Option(..., "--record-type", help="Record type of that record, e.g. customer"),
    output: str = Format,
):
    """Get the approval details of one non-monetary record."""
    from dualentry_cli.main import get_client

    client = get_client()
    data = client.get(f"/inbox/records/{record_id}/", params={"record_type": record_type})
    _show_detail(data, "inbox-record", output)
