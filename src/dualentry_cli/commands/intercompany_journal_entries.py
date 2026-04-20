"""Intercompany journal entry commands."""

from __future__ import annotations

from pathlib import Path

import typer

from dualentry_cli.commands import Format, _load_json_file, _strip_record_prefix, make_resource_app
from dualentry_cli.output import format_output

app = make_resource_app("intercompany journal entries", "intercompany-journal-entry", "intercompany-journal-entries", has_number=True)

_PATH = "intercompany-journal-entries"
_RESOURCE = "intercompany-journal-entry"


@app.command("validate")
def validate_cmd(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file to validate"),
):
    """Validate an intercompany journal entry payload (client-side)."""
    from decimal import Decimal, InvalidOperation

    payload = _load_json_file(file)
    errors: list[str] = []

    items = payload.get("items")
    if not items or not isinstance(items, list):
        errors.append("Payload must contain a non-empty 'items' array.")
    else:
        company_ids = set()
        total_debits = Decimal(0)
        total_credits = Decimal(0)

        for i, item in enumerate(items):
            cid = item.get("company_id")
            if cid is not None:
                company_ids.add(cid)

            try:
                debit = Decimal(str(item.get("debit", "0")))
                credit = Decimal(str(item.get("credit", "0")))
            except (InvalidOperation, TypeError):
                errors.append(f"Item {i}: invalid debit/credit value.")
                continue

            total_debits += debit
            total_credits += credit

        if not errors:
            if len(company_ids) < 2:
                errors.append("Intercompany journal entries require lines across at least two distinct companies.")

            total_debits = total_debits.quantize(Decimal("0.01"))
            total_credits = total_credits.quantize(Decimal("0.01"))
            if total_debits != total_credits:
                errors.append(f"Total debits ({total_debits}) must equal total credits ({total_credits}).")

    if errors:
        for err in errors:
            typer.secho(f"  \u2717 {err}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho("  \u2713 Valid", fg=typer.colors.GREEN)


@app.command("post")
def post_cmd(
    number: str = typer.Argument(help="Record number of the draft IJE to post"),
    output: str = Format,
):
    """Post a draft intercompany journal entry."""
    from dualentry_cli.main import get_client

    client = get_client()
    stripped = _strip_record_prefix(number)
    data = client.get(f"/{_PATH}/{stripped}/")

    current_status = data.get("record_status", "")
    if current_status != "draft":
        typer.secho(f"  \u2717 Cannot post: record is '{current_status}', only draft records can be posted.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    data["record_status"] = "posted"
    result = client.put(f"/{_PATH}/{stripped}/", json=data)
    format_output(result, resource=_RESOURCE, fmt=output)


_TEMPLATE = {
    "date": "2026-01-01",
    "memo": "Intercompany transfer",
    "currency_iso_4217_code": "USD",
    "exchange_rate": "1.00000000",
    "record_status": "draft",
    "items": [
        {
            "company_id": 1,
            "account_number": 1000,
            "debit": "1000.00",
            "credit": "0.00",
            "memo": "",
            "position": 0,
            "eliminate": True,
        },
        {
            "company_id": 2,
            "account_number": 2000,
            "debit": "0.00",
            "credit": "1000.00",
            "memo": "",
            "position": 1,
            "eliminate": True,
        },
    ],
}


@app.command("template")
def template_cmd(
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Write template to file instead of stdout"),
):
    """Output a sample intercompany journal entry JSON template."""
    import json as json_mod

    content = json_mod.dumps(_TEMPLATE, indent=2)
    if output_file:
        output_file.write_text(content + "\n")
        typer.secho(f"Template written to {output_file}", fg=typer.colors.GREEN)
    else:
        typer.echo(content)
