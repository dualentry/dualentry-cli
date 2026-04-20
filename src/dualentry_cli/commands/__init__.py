"""Command factory for DualEntry CLI resources."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.output import _RECORD_PREFIX, format_output

# ── Shared option defaults ──────────────────────────────────────────

Limit = typer.Option(20, "--limit", "-l", help="Max items to return")
Offset = typer.Option(0, "--offset", help="Offset for pagination")
AllPages = typer.Option(False, "--all", "-a", help="Fetch all pages")
Search = typer.Option(None, "--search", "-s", help="Free text search")
Status = typer.Option(None, "--status", help="Filter by status (draft, posted, archived)")
StartDate = typer.Option(None, "--start-date", help="Filter from date (YYYY-MM-DD)")
EndDate = typer.Option(None, "--end-date", help="Filter to date (YYYY-MM-DD)")
Format = typer.Option("human", "--format", "-o", help="Output format: human or json")


_PREFIX_TO_RESOURCE = {v: k for k, v in _RECORD_PREFIX.items()}


def _resolve_by_internal_id(client, path: str, value: str) -> dict | None:
    """Try to find a record by internal_id when lookup by number fails."""
    if not value.isdigit():
        return None
    try:
        data = client.get(f"/{path}/", params={"search": value, "limit": 5})
    except Exception:
        return None
    for item in data.get("items", []):
        if str(item.get("internal_id")) == value:
            number = item.get("number")
            if number is not None:
                return client.get(f"/{path}/{number}/")
    return None


def _strip_record_prefix(number: str) -> str:
    """Strip display prefix from a record number (e.g. 'JE-1619031' → '1619031')."""
    if "-" in number:
        prefix, _, rest = number.partition("-")
        if prefix.upper() in _PREFIX_TO_RESOURCE and rest.isdigit():
            return rest
    return number


def _build_filter_params(
    search: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Build filter query params, omitting None values."""
    params: dict = {}
    if search:
        params["search"] = search
    if status:
        params["record_status"] = status
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return params


def _do_list(client, path: str, resource: str, limit: int, offset: int, all_pages: bool, output: str, **filters):
    """Shared list logic for all resources."""
    params = _build_filter_params(**filters)
    if all_pages:
        data = client.paginate(f"/{path}/", params=params)
    else:
        params.update({"limit": limit, "offset": offset})
        data = client.get(f"/{path}/", params=params)
    format_output(data, resource=resource, fmt=output)


def _load_json_file(file: Path) -> dict:
    """Load and validate a JSON file, with helpful error messages."""
    if not file.exists():
        typer.secho(f"Error: File not found: {file}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    try:
        content = file.read_text()
    except OSError as e:
        typer.secho(f"Error: Cannot read file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        typer.secho(f"Error: Invalid JSON in {file.name}: {e.msg} at line {e.lineno}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


# ── Post command helpers ───────────────────────────────────────────

_WRITABLE_FIELDS = {"date", "transaction_date", "memo", "currency_iso_4217_code", "exchange_rate", "record_status", "items", "attachments"}
_WRITABLE_ITEM_FIELDS = {"id", "company_id", "account_number", "debit", "credit", "memo", "position", "classifications", "customer_id", "vendor_id", "currency", "eliminate"}


def _strip_to_writable(data: dict) -> dict:
    payload = {k: v for k, v in data.items() if k in _WRITABLE_FIELDS}
    if "items" in payload:
        payload["items"] = [{k: v for k, v in item.items() if k in _WRITABLE_ITEM_FIELDS} for item in payload["items"]]
    return payload


# ── Factory ─────────────────────────────────────────────────────────


def make_resource_app(
    name: str,
    resource: str,
    path: str,
    has_create: bool = True,
    has_update: bool = True,
    has_delete: bool = False,
    has_number: bool = False,
    has_post: bool = False,
    template: dict | None = None,
    validate_fn: Callable[[Path], None] | None = None,
) -> typer.Typer:
    """Create a Typer app for a standard CRUD resource."""
    app = typer.Typer(help=f"Manage {name}", no_args_is_help=True, cls=HelpfulGroup)

    @app.command("list")
    def list_cmd(
        limit: int = Limit,
        offset: int = Offset,
        all_pages: bool = AllPages,
        search: str | None = Search,
        status: str | None = Status,
        start_date: str | None = StartDate,
        end_date: str | None = EndDate,
        output: str = Format,
    ):
        from dualentry_cli.main import get_client

        client = get_client()
        _do_list(client, path, resource, limit, offset, all_pages, output, search=search, status=status, start_date=start_date, end_date=end_date)

    list_cmd.__doc__ = f"List {name}."

    if has_number:

        @app.command("get")
        def get_cmd_auto(
            value: str = typer.Argument(help="Record number (#) or ID (e.g. JE-1619031)"),
            output: str = Format,
        ):
            """Try by number first, fall back to ID lookup on 404."""
            from dualentry_cli.client import APIError
            from dualentry_cli.main import get_client

            client = get_client()
            stripped = _strip_record_prefix(value)
            try:
                data = client.get(f"/{path}/{stripped}/")
            except APIError as e:
                if e.status_code != 404:
                    raise
                data = _resolve_by_internal_id(client, path, stripped)
                if data is None:
                    raise
            format_output(data, resource=resource, fmt=output)

        get_cmd_auto.__doc__ = f"Get a {resource} by number or ID."

        @app.command("get-number")
        def get_cmd_by_number(
            number: str = typer.Argument(help="Record number (the # column)"),
            output: str = Format,
        ):
            from dualentry_cli.main import get_client

            client = get_client()
            data = client.get(f"/{path}/{_strip_record_prefix(number)}/")
            format_output(data, resource=resource, fmt=output)

        get_cmd_by_number.__doc__ = f"Get a {resource} by number."

        @app.command("get-id")
        def get_cmd_by_id(
            record_id: str = typer.Argument(help="Record ID (e.g. JE-1619031 or 1619031)"),
            output: str = Format,
        ):
            from dualentry_cli.client import APIError
            from dualentry_cli.main import get_client

            client = get_client()
            stripped = _strip_record_prefix(record_id)
            data = _resolve_by_internal_id(client, path, stripped)
            if data is None:
                raise APIError(404, "Resource not found. Check the ID and try again.")
            format_output(data, resource=resource, fmt=output)

        get_cmd_by_id.__doc__ = f"Get a {resource} by ID."
    else:

        @app.command("get")
        def get_cmd(
            record_id: str = typer.Argument(help="Record ID"),
            output: str = Format,
        ):
            from dualentry_cli.main import get_client

            client = get_client()
            data = client.get(f"/{path}/{record_id}/")
            format_output(data, resource=resource, fmt=output)

        get_cmd.__doc__ = f"Get a {resource} by ID."

    if has_create:

        @app.command("create")
        def create_cmd(
            file: Path = typer.Option(..., "--file", "-f", help="JSON file with record data"),
            output: str = Format,
        ):
            from dualentry_cli.main import get_client

            payload = _load_json_file(file)
            client = get_client()
            data = client.post(f"/{path}/", json=payload)
            format_output(data, resource=resource, fmt=output)

        create_cmd.__doc__ = f"Create a {resource} from a JSON file."

    if has_update:

        @app.command("update")
        def update_cmd(
            record_id: str = typer.Argument(help="Record ID"),
            file: Path = typer.Option(..., "--file", "-f", help="JSON file with update data"),
            output: str = Format,
        ):
            from dualentry_cli.main import get_client

            payload = _load_json_file(file)
            client = get_client()
            data = client.put(f"/{path}/{record_id}/", json=payload)
            format_output(data, resource=resource, fmt=output)

        update_cmd.__doc__ = f"Update a {resource}."

    if has_delete:

        @app.command("delete")
        def delete_cmd(
            record_id: str = typer.Argument(help="Record ID"),
        ):
            from dualentry_cli.main import get_client

            client = get_client()
            client.delete(f"/{path}/{record_id}/")
            typer.echo(f"{resource.replace('-', ' ').title()} {record_id} deleted.")

        delete_cmd.__doc__ = f"Delete a {resource}."

    if validate_fn is not None:

        @app.command("validate")
        def validate_cmd(
            file: Path = typer.Option(..., "--file", "-f", help="JSON file to validate"),
        ):
            validate_fn(file)

        validate_cmd.__doc__ = f"Validate a {resource} payload (client-side)."

    if has_post:

        @app.command("post")
        def post_cmd(
            number: str = typer.Argument(help="Record number of the draft to post"),
            output: str = Format,
        ):
            from dualentry_cli.main import get_client

            client = get_client()
            stripped = _strip_record_prefix(number)
            data = client.get(f"/{path}/{stripped}/")

            current_status = data.get("record_status", "")
            if current_status != "draft":
                typer.secho(f"  \u2717 Cannot post: record is '{current_status}', only draft records can be posted.", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=1)

            payload = _strip_to_writable(data)
            payload["record_status"] = "posted"
            result = client.put(f"/{path}/{stripped}/", json=payload)
            format_output(result, resource=resource, fmt=output)

        post_cmd.__doc__ = f"Post a draft {resource}."

    if template is not None:

        @app.command("template")
        def template_cmd(
            output_file: Path | None = typer.Option(None, "--output", "-o", help="Write template to file instead of stdout"),
        ):
            content = json.dumps(template, indent=2)
            if output_file:
                output_file.write_text(content + "\n")
                typer.secho(f"Template written to {output_file}", fg=typer.colors.GREEN)
            else:
                typer.echo(content)

        template_cmd.__doc__ = f"Output a sample {resource} JSON template."

    return app
