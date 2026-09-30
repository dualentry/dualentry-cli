"""Quote (CPQ) commands."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import typer

from dualentry_cli.commands import AllPages, Format, Limit, Offset, Search, Status
from dualentry_cli.commands.actions import load_json_file, make_action_app, run_list
from dualentry_cli.output import format_output

app = make_action_app("Manage quotes (requires the CPQ subscription). Approvers approve or reject quotes in DualEntry; the API does not render quote PDFs or payment schedules.")

_REFERENCE_RE = re.compile(r"^QT-?(\d+)$", re.IGNORECASE)
_DISPLAY_OPTION_KEYS = ("headline_total", "total_rows", "year_by_year")

QUOTE_TEMPLATE = {
    "company_id": 1,
    "customer_id": 1,
    "email": "buyer@example.com",
    "currency_iso_4217_code": "USD",
    "close_date": "2026-01-15",
    "contract_start_date": "2026-02-01",
    "contract_end_type": "after",
    "number_of_months": 12,
    "record_status": "draft",
    "items": [
        {"item_id": 1, "quantity": 1, "rate": 5000, "position": 1, "memo": "Implementation"},
        {"item_id": 2, "quantity": 10, "rate": 50, "position": 2, "billing_frequency": "monthly", "memo": "Seats, per month"},
    ],
    "recipients": [
        {"side": "buyer", "name": "Ana Diaz", "email": "buyer@example.com", "position": 1},
        {"side": "company", "name": "Sam Lee", "email": "sales@example.com", "position": 1},
    ],
}

Quote = typer.Argument(help="Quote number (e.g. 12) or the QT- ID shown in DualEntry (e.g. QT-45)")
DisplayOptions = typer.Option(
    None,
    "--display-options",
    help='Quote document settings as JSON, e.g. \'{"headline_total": "annual", "total_rows": ["one_time", "tcv"], "year_by_year": true}\'',
)


def _client():
    from dualentry_cli.main import get_client

    return get_client()


def _quote_number(client, reference: str) -> str:
    """Resolve a quote number or QT-<id> reference to the quote number the API routes on."""
    raw = reference.strip()
    if match := _REFERENCE_RE.match(raw):
        from dualentry_cli.client import APIError

        items = client.get("/quotes/", params={"id": int(match.group(1)), "limit": 1}).get("items", [])
        if not items:
            raise APIError(404, f"Quote {raw} not found.")
        return str(items[0]["number"])
    if raw.isdigit():
        return raw
    typer.secho(f"Error: '{reference}' is not a quote number or QT- ID.", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=2)


def _display_options(value: str | None) -> dict:
    if not value:
        return {}
    try:
        options = json.loads(value)
    except json.JSONDecodeError as e:
        typer.secho(f"Error: --display-options is not valid JSON: {e.msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from None
    if not isinstance(options, dict) or set(options) - set(_DISPLAY_OPTION_KEYS):
        typer.secho(f"Error: --display-options accepts {', '.join(_DISPLAY_OPTION_KEYS)}.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    return {f"document_{key}": option for key, option in options.items()}


@app.command("list")
def list_quotes(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    status: str | None = Status,
    approval_status: str | None = typer.Option(None, "--approval-status", help="draft, pending_approval, approved or rejected"),
    company: str | None = typer.Option(None, "--company", "-c", help="Filter by company ID"),
    customer: str | None = typer.Option(None, "--customer", help="Filter by customer ID"),
    valid_from: str | None = typer.Option(None, "--valid-from", help="Valid until on or after (YYYY-MM-DD)"),
    valid_to: str | None = typer.Option(None, "--valid-to", help="Valid until on or before (YYYY-MM-DD)"),
    ordering: str | None = typer.Option(None, "--ordering", help="Sort field, e.g. -amount, valid_until, customer__name"),
    output: str = Format,
):
    """List quotes."""
    run_list(
        "quotes",
        resource="quote",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        search=search,
        status=status,
        approval_status=approval_status,
        company_id=company,
        customer_id=customer,
        valid_until_from=valid_from,
        valid_until_to=valid_to,
        ordering=ordering,
    )


@app.command("get")
def get_quote(quote: str = Quote, output: str = Format):
    """Get a quote with its lines, recipients, approval status, and totals."""
    client = _client()
    format_output(client.get(f"/quotes/{_quote_number(client, quote)}/"), resource="quote", fmt=output)


@app.command("create")
def create_quote(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with the quote (see `dualentry quotes template`)"),
    display_options: str | None = DisplayOptions,
    output: str = Format,
):
    """
    Create a quote from a JSON file.

    record_status "posted" (the default) submits the quote for approval; "draft" saves it.
    On recurring lines, rate is the price per billing period.
    """
    payload = load_json_file(file) | _display_options(display_options)
    format_output(_client().post("/quotes/", json=payload), resource="quote", fmt=output)


@app.command("update")
def update_quote(
    quote: str = Quote,
    file: Path | None = typer.Option(None, "--file", "-f", help="JSON file with the fields to change"),
    display_options: str | None = DisplayOptions,
    output: str = Format,
):
    """
    Update a quote. Only the fields you send change.

    Sending "items" or "recipients" replaces the saved list: include each one to keep, with its id.
    A line sent without billing fields becomes a one-time line.
    """
    payload = (load_json_file(file) if file else {}) | _display_options(display_options)
    if not payload:
        typer.secho("Error: provide --file and/or --display-options.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    client = _client()
    format_output(client.patch(f"/quotes/{_quote_number(client, quote)}/", json=payload), resource="quote", fmt=output)


@app.command("submit")
def submit_quote(quote: str = Quote, output: str = Format):
    """Submit a draft or rejected quote for approval."""
    client = _client()
    format_output(client.patch(f"/quotes/{_quote_number(client, quote)}/", json={"record_status": "posted"}), resource="quote", fmt=output)


@app.command("send")
def send_quote(
    quote: str = Quote,
    to: list[str] = typer.Option([], "--to", help="Recipient; repeat for more. Defaults to the quote's buyers"),
    cc: list[str] = typer.Option([], "--cc", help="CC address; repeat for more"),
    bcc: list[str] = typer.Option([], "--bcc", help="BCC address; repeat for more"),
    subject: str | None = typer.Option(None, "--subject", help="Defaults to the organization's quote email subject"),
    message: str | None = typer.Option(None, "--message", help="Defaults to the organization's quote email message"),
    reply_to: str | None = typer.Option(None, "--reply-to", help="Defaults to the organization's reply-to address"),
    pdf: Path | None = typer.Option(None, "--pdf", help="Quote PDF to attach (download it from DualEntry)"),
    no_pdf: bool = typer.Option(False, "--no-pdf", help="Send without attaching the PDF"),
):
    """Email an approved quote to its buyers and mark it sent."""
    if pdf and no_pdf:
        typer.secho("Error: use --pdf or --no-pdf, not both.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    body: dict = {"to_emails": to, "cc_emails": cc, "bcc_emails": bcc, "subject": subject, "message": message, "reply_to": reply_to}
    if pdf:
        if not pdf.exists():
            typer.secho(f"Error: File not found: {pdf}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        body |= {"attach_pdf": True, "pdf_content": base64.b64encode(pdf.read_bytes()).decode()}
    elif no_pdf:
        body["attach_pdf"] = False
    client = _client()
    number = _quote_number(client, quote)
    client.post(f"/quotes/{number}/send/", json={key: value for key, value in body.items() if value not in (None, [])})
    typer.secho(f"Quote {number} sent.", fg=typer.colors.GREEN)


@app.command("template")
def template(output_file: Path | None = typer.Option(None, "--output", "-o", help="Write the template to a file instead of stdout")):
    """Output a sample quote JSON file."""
    content = json.dumps(QUOTE_TEMPLATE, indent=2)
    if output_file:
        output_file.write_text(content + "\n")
        typer.secho(f"Template written to {output_file}", fg=typer.colors.GREEN)
    else:
        typer.echo(content)
