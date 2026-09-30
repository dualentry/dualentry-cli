"""Statistical journal commands (custom list filters and attachment upload)."""

from __future__ import annotations

from pathlib import Path

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import (
    AllPages,
    Format,
    Limit,
    Offset,
    Search,
    Status,
    _do_list,
    _load_json_file,
    _strip_record_prefix,
    _supplied,
)
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage statistical journals", no_args_is_help=True, cls=HelpfulGroup)


def _csv_ints(value: str | None) -> list[int] | None:
    if not value:
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _csv_strings(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def _build_list_filters(
    *,
    search: str | None,
    status: str | None,
    company: str | None,
    date_start: str | None,
    date_end: str | None,
    period_start: str | None,
    period_end: str | None,
    number: str | None,
    account_id: str | None,
    account_number: str | None,
    line_account_id: str | None,
    line_account_number: str | None,
    updated_after: str | None,
    updated_before: str | None,
    ordering: str | None,
) -> dict:
    params: dict = {}
    if search:
        params["search"] = search
    if status:
        params["record_status"] = status
    if company:
        params["company_id"] = company
    if date_start:
        params["date_start"] = date_start
    if date_end:
        params["date_end"] = date_end
    if period_start:
        params["period_start"] = period_start
    if period_end:
        params["period_end"] = period_end
    if number:
        params["number"] = _csv_ints(number)
    if account_id:
        params["account_id"] = _csv_ints(account_id)
    if account_number:
        params["account_number"] = _csv_strings(account_number)
    if line_account_id:
        params["line_account_id"] = _csv_ints(line_account_id)
    if line_account_number:
        params["line_account_number"] = _csv_strings(line_account_number)
    if updated_after:
        params["updated_after"] = updated_after
    if updated_before:
        params["updated_before"] = updated_before
    if ordering:
        params["ordering"] = ordering
    return params


@app.command("list")
def list_cmd(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    status: str | None = Status,
    company: str | None = typer.Option(None, "--company", "-c", help="Filter by company ID"),
    date_start: str | None = typer.Option(None, "--date-start", help="Filter from journal date (YYYY-MM-DD)"),
    date_end: str | None = typer.Option(None, "--date-end", help="Filter to journal date (YYYY-MM-DD)"),
    period_start: str | None = typer.Option(None, "--period-start", help="Filter from period start (YYYY-MM-DD)"),
    period_end: str | None = typer.Option(None, "--period-end", help="Filter to period end (YYYY-MM-DD)"),
    number: str | None = typer.Option(None, "--number", help="Filter by record number(s), comma-separated"),
    account_id: str | None = typer.Option(None, "--account-id", help="Filter by account ID(s), comma-separated"),
    account_number: str | None = typer.Option(None, "--account-number", help="Filter by account number(s), comma-separated"),
    line_account_id: str | None = typer.Option(None, "--line-account-id", help="Filter by line account ID(s), comma-separated"),
    line_account_number: str | None = typer.Option(None, "--line-account-number", help="Filter by line account number(s), comma-separated"),
    updated_after: str | None = typer.Option(None, "--updated-after", help="Updated after timestamp (ISO 8601)"),
    updated_before: str | None = typer.Option(None, "--updated-before", help="Updated before timestamp (ISO 8601)"),
    ordering: str | None = typer.Option(None, "--ordering", help="Sort order (API field name, optional leading -)"),
    output: str = Format,
):
    """List statistical journals."""
    from dualentry_cli.main import get_client

    client = get_client()
    filters = _build_list_filters(
        search=_supplied(search),
        status=_supplied(status),
        company=_supplied(company),
        date_start=_supplied(date_start),
        date_end=_supplied(date_end),
        period_start=_supplied(period_start),
        period_end=_supplied(period_end),
        number=_supplied(number),
        account_id=_supplied(account_id),
        account_number=_supplied(account_number),
        line_account_id=_supplied(line_account_id),
        line_account_number=_supplied(line_account_number),
        updated_after=_supplied(updated_after),
        updated_before=_supplied(updated_before),
        ordering=_supplied(ordering),
    )
    _do_list(
        client,
        "statistical-journals",
        "statistical-journal",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        status_param="record_status",
        **filters,
    )


@app.command("get")
def get_cmd(
    value: str = typer.Argument(help="Record number (#) or prefixed number (e.g. SJ-3)"),
    output: str = Format,
):
    """Get a statistical journal by number."""
    from dualentry_cli.main import get_client

    client = get_client()
    data = client.get(f"/statistical-journals/{_strip_record_prefix(value)}/")
    format_output(data, resource="statistical-journal", fmt=output)


@app.command("create")
def create_cmd(
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with record data"),
    output: str = Format,
):
    """Create a statistical journal from a JSON file."""
    from dualentry_cli.main import get_client

    payload = _load_json_file(file)
    client = get_client()
    data = client.post("/statistical-journals/", json=payload)
    format_output(data, resource="statistical-journal", fmt=output)


@app.command("update")
def update_cmd(
    number: str = typer.Argument(help="Record number of the journal to update"),
    file: Path = typer.Option(..., "--file", "-f", help="JSON file with update data"),
    output: str = Format,
):
    """Update a statistical journal."""
    from dualentry_cli.main import get_client

    payload = _load_json_file(file)
    client = get_client()
    data = client.put(f"/statistical-journals/{_strip_record_prefix(number)}/", json=payload)
    format_output(data, resource="statistical-journal", fmt=output)


@app.command("add-attachments")
def add_attachments_cmd(
    number: str = typer.Argument(help="Record number of the journal"),
    file: list[Path] = typer.Option(..., "--file", "-f", help="Attachment file(s) to upload", exists=True, readable=True),
    output: str = Format,
):
    """Upload attachment file(s) to a statistical journal."""
    from dualentry_cli.main import get_client

    client = get_client()
    stripped = _strip_record_prefix(number)
    multipart = [("files", (path.name, path.read_bytes())) for path in file]
    data = client.post(f"/statistical-journals/{stripped}/attachments/", files=multipart)
    format_output(data, resource="statistical-journal", fmt=output)
