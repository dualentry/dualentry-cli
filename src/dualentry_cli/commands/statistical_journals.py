"""Statistical journal commands (custom list filters and attachment upload)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import (
    AllPages,
    Format,
    Limit,
    Offset,
    Search,
    Status,
    _load_json_file,
    _strip_record_prefix,
)
from dualentry_cli.commands.actions import run_list
from dualentry_cli.output import format_output

app = typer.Typer(help="Manage statistical journals", no_args_is_help=True, cls=HelpfulGroup)


def _parse_csv_ints(value: str) -> list[int] | None:
    """Parse a comma-separated list of integers for list filters."""
    raw = value.strip()
    if not raw:
        return None
    result: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            result.append(int(token))
        except ValueError:
            raise typer.BadParameter(f"expected comma-separated integers, got {token!r}") from None
    return result or None


def _csv_ints_option(flag: str, *, help: str) -> typer.Option:
    return typer.Option(flag, parser=_parse_csv_ints, help=help)


def _csv_strings(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


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
    number: Annotated[
        list[int] | None,
        _csv_ints_option("--number", help="Filter by record number(s), comma-separated"),
    ] = None,
    account_id: Annotated[
        list[int] | None,
        _csv_ints_option("--account-id", help="Filter by account ID(s), comma-separated"),
    ] = None,
    account_number: str | None = typer.Option(None, "--account-number", help="Filter by account number(s), comma-separated"),
    line_account_id: Annotated[
        list[int] | None,
        _csv_ints_option("--line-account-id", help="Filter by line account ID(s), comma-separated"),
    ] = None,
    line_account_number: str | None = typer.Option(None, "--line-account-number", help="Filter by line account number(s), comma-separated"),
    updated_after: str | None = typer.Option(None, "--updated-after", help="Updated after timestamp (ISO 8601)"),
    updated_before: str | None = typer.Option(None, "--updated-before", help="Updated before timestamp (ISO 8601)"),
    ordering: str | None = typer.Option(None, "--ordering", help="Sort order (API field name, optional leading -)"),
    output: str = Format,
):
    """List statistical journals."""
    run_list(
        "statistical-journals",
        resource="statistical-journal",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        search=search,
        status=status,
        company_id=company or None,
        date_start=date_start or None,
        date_end=date_end or None,
        period_start=period_start or None,
        period_end=period_end or None,
        number=number,
        account_id=account_id,
        account_number=_csv_strings(account_number),
        line_account_id=line_account_id,
        line_account_number=_csv_strings(line_account_number),
        updated_after=updated_after or None,
        updated_before=updated_before or None,
        ordering=ordering or None,
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
