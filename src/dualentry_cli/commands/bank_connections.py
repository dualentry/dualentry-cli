from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from dualentry_cli.commands import AllPages, Format, Limit, Offset
from dualentry_cli.commands.actions import load_json_file, make_action_app, run_get, run_list, run_post
from dualentry_cli.output import format_output

app = make_action_app("Manage bank connections")
accounts_app = make_action_app("Manage accounts under a bank connection")
transactions_app = make_action_app("Push bank transactions for a registered account")
app.add_typer(accounts_app, name="accounts")
app.add_typer(transactions_app, name="transactions")


@app.command("list")
def list_connections(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    updated_after: datetime | None = typer.Option(
        None,
        "--updated-after",
        help="Only connections updated at or after this time (ISO 8601)",
    ),
    updated_before: datetime | None = typer.Option(
        None,
        "--updated-before",
        help="Only connections updated at or before this time (ISO 8601)",
    ),
    output: str = Format,
):
    """List bank connections."""
    run_list(
        "bank-connections",
        resource="bank-connection",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        updated_after=updated_after.isoformat() if updated_after else None,
        updated_before=updated_before.isoformat() if updated_before else None,
    )


@app.command("get")
def get_connection(
    connection_id: int = typer.Argument(help="DualEntry bank connection ID"),
    output: str = Format,
):
    """Get one bank connection by ID."""
    run_get(f"/bank-connections/{connection_id}/", resource="bank-connection", output=output)


@app.command("create")
def create_connection(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with connection registration body"),
    output: str = Format,
):
    """Register a bank connection (and optional accounts)."""
    body = load_json_file(file)
    run_post("/bank-connections/", resource="bank-connection", output=output, body=body)


@app.command("delete")
def delete_connection(
    connection_id: int = typer.Argument(help="DualEntry bank connection ID to unregister"),
):
    """Unregister a customer API bank connection."""
    from dualentry_cli.main import get_client

    get_client().delete(f"/bank-connections/{connection_id}/")
    typer.echo(f"Bank connection {connection_id} deleted.")


@accounts_app.command("list")
def list_accounts(
    connection_id: int = typer.Argument(help="DualEntry bank connection ID"),
    output: str = Format,
):
    """List accounts registered under a bank connection."""
    from dualentry_cli.main import get_client

    data = get_client().get(f"/bank-connections/{connection_id}/accounts/")
    if isinstance(data, list):
        data = {"items": data, "count": len(data)}
    format_output(data, resource="bank-connection-account", fmt=output)


@accounts_app.command("create")
def create_accounts(
    connection_id: int = typer.Argument(help="DualEntry bank connection ID"),
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with accounts array body"),
    output: str = Format,
):
    """Register accounts under an existing bank connection."""
    body = load_json_file(file)
    run_post(
        f"/bank-connections/{connection_id}/accounts/",
        resource="bank-connection",
        output=output,
        body=body,
    )


@transactions_app.command("push")
def push_transactions(
    financial_account_id: int = typer.Argument(help="DualEntry financial account ID"),
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with transactions batch body"),
    output: str = Format,
):
    """Push a batch of bank transactions for a registered account."""
    body = load_json_file(file)
    run_post(
        f"/bank-connections/accounts/{financial_account_id}/transactions/",
        resource="bank-connection",
        output=output,
        body=body,
    )


_TEMPLATE_CONNECTION = {
    "connection_source_id": "conn-1",
    "institution_name": "Customer Bank",
    "accounts": [
        {
            "account_id": "acct-checking",
            "account_name": "Checking",
            "truncated_account_number": "1234",
        },
        {
            "account_id": "acct-savings",
            "account_name": "Savings",
            "currency_iso_4217_code": "USD",
        },
    ],
}
_TEMPLATE_ACCOUNTS = {
    "accounts": [
        {
            "account_id": "acct-checking",
            "account_name": "Checking",
            "truncated_account_number": "1234",
        }
    ]
}
_TEMPLATE_TRANSACTIONS = {
    "transactions": [
        {
            "external_trx_id": "tx-1",
            "account_id": "acct-checking",
            "date": "2026-01-15T00:00:00",
            "amount": "10.00",
            "description": "Deposit",
            "is_posted": True,
            "posted_at": "2026-01-15T00:00:00",
            "counterparty": "Example Merchant",
        }
    ]
}


@app.command("template")
def template_cmd(
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Write template to file instead of stdout"),
    template_type: str = typer.Option(
        "connection",
        "--type",
        "-t",
        help='Template type: "connection", "accounts", or "transactions"',
    ),
):
    """Output a sample bank-connections JSON template."""
    if template_type == "connection":
        template = _TEMPLATE_CONNECTION
    elif template_type == "accounts":
        template = _TEMPLATE_ACCOUNTS
    elif template_type == "transactions":
        template = _TEMPLATE_TRANSACTIONS
    else:
        raise typer.BadParameter(f"Unknown template type: {template_type}")

    content = json.dumps(template, indent=2)
    if output_file:
        output_file.write_text(content + "\n")
        typer.secho(f"Template written to {output_file}", fg=typer.colors.GREEN)
    else:
        typer.echo(content)
