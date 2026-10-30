"""Command factory for DualEntry CLI resources."""

from __future__ import annotations

import json
import shlex
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from dualentry_cli.cli import HelpfulGroup, make_list_command_cls
from dualentry_cli.client import _MAX_PAGES
from dualentry_cli.output import _RECORD_PREFIX, format_output

if TYPE_CHECKING:
    from typer.models import OptionInfo

# Filter flags `list` can offer, with every option spelling each one accepts.
FILTER_OPTIONS = {
    "search": ("--search", "-s"),
    "status": ("--status",),
    "start_date": ("--start-date",),
    "end_date": ("--end-date",),
    "company": ("--company", "-c"),
    "customer": ("--customer",),
    "vendor": ("--vendor",),
}
ALL_FILTERS = frozenset(FILTER_OPTIONS)

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


def _supplied(value) -> str | None:
    """Return a flag's value, or None when a stripped option left its OptionInfo sentinel unbound."""
    return value if isinstance(value, str) else None


def _parse_csv_ints(value: str) -> list[int]:
    """
    Parse one occurrence of a comma-separated integer filter, e.g. `3,4`.

    Args:
        value: The raw option value as typed on the command line.

    Returns:
        The integers in the order given.

    Raises:
        typer.BadParameter: If the value holds no integers, or any token is not one.
            An empty value is rejected, not ignored: dropping the filter would
            widen the query to every row.

    """
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not tokens:
        raise typer.BadParameter("expected comma-separated integers, got an empty value")
    ints: list[int] = []
    for token in tokens:
        try:
            ints.append(int(token))
        except ValueError as e:
            raise typer.BadParameter(f"expected comma-separated integers, got {token!r}") from e
    return ints


def _flatten_csv_ints(chunks: Sequence[list[int]] | None) -> list[int] | None:
    """
    Merge every occurrence of a repeatable CSV option into one flat list.

    Args:
        chunks: One parsed list per occurrence of the flag, or None when it was not passed.

    Returns:
        The merged integers, or None when the flag was not passed, so the filter is omitted.

    """
    merged = [n for chunk in chunks or () for n in chunk]
    return merged or None


def csv_ints_option(flag: str, *, help_text: str) -> OptionInfo:
    """
    Build a `--flag 1,2,3` option that typer hands to the command as `list[int] | None`.

    A `list[int]` annotation makes typer treat the option as repeatable and run
    `parser` once per occurrence, which yields `[[1, 2, 3]]`. The callback flattens
    that, so `--flag 1,2 --flag 3` also works.

    Args:
        flag: The option spelling, e.g. `"--id"`.
        help_text: The `--help` description.

    Returns:
        The option, for use inside `Annotated[list[int] | None, ...]`.

    """
    return typer.Option(flag, parser=_parse_csv_ints, callback=_flatten_csv_ints, metavar="<ids>", help=help_text)


def _build_filter_params(
    search: str | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    status_param: str = "record_status",
    **extra,
) -> dict:
    """Build filter query params, omitting None values."""
    params: dict = {}
    if search:
        params["search"] = search
    if status:
        params[status_param] = status
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params.update({key: value for key, value in extra.items() if value is not None})
    return params


# How a filter kwarg is spelled in the --all resume hint: a value-taking flag, or an
# (on, off) pair for a `--x/--no-x` boolean.
ResumeFlag = str | tuple[str, str]

# Map _do_list filter kwargs to CLI flags for the --all resume hint. Commands with
# their own filters pass a mapping of their own; a filter left out of it would be
# missing from the hint, and the "same filters" command would return other rows.
_FILTER_CLI_FLAGS: dict[str, ResumeFlag] = {
    "search": "--search",
    "status": "--status",
    "start_date": "--start-date",
    "end_date": "--end-date",
    "company_id": "--company",
    "customer_id": "--customer",
    "vendor_id": "--vendor",
}


def _resume_all_command(
    path: str,
    next_offset: int,
    filters: Mapping[str, object],
    flags: Mapping[str, ResumeFlag] = _FILTER_CLI_FLAGS,
) -> str:
    """
    Build a copy-paste dualentry list --all command that continues from next_offset.

    Args:
        path: The API path, whose segments are also the CLI command path.
        next_offset: Where the next run should start.
        filters: The filter kwargs the truncated run used.
        flags: How each filter kwarg is spelled on the command line.

    Returns:
        A shell-quoted command line.

    """
    parts = ["dualentry", *path.split("/"), "list", "--all", "--offset", str(next_offset)]
    for key, flag in flags.items():
        value = filters.get(key)
        if value is None:
            continue
        if isinstance(flag, tuple):
            on, off = flag
            parts.append(on if value else off)
        elif isinstance(value, list):
            parts.extend([flag, ",".join(map(str, value))])
        else:
            parts.extend([flag, str(value)])
    return shlex.join(parts)


def _warn_all_truncated(
    path: str,
    *,
    fetched_through: int,
    total: int,
    next_offset: int,
    filters: Mapping[str, object],
    flags: Mapping[str, ResumeFlag] = _FILTER_CLI_FLAGS,
    resume: str | None = None,
) -> None:
    """
    Tell the user --all stopped early and how to continue.

    Args:
        path: The API path, used to rebuild the command when `resume` is not given.
        fetched_through: How many items the run reached.
        total: The API's total count.
        next_offset: Where the next run should start.
        filters: The filter kwargs the truncated run used.
        flags: How each filter kwarg is spelled on the command line.
        resume: A ready-made resume command, for commands whose CLI shape is not
            `<api path> list` (e.g. `webhooks deliveries <uuid>`).

    """
    cmd = resume or _resume_all_command(path, next_offset, filters, flags)
    typer.secho(
        f"Warning: reached {fetched_through} of {total} items; stopped at the {_MAX_PAGES}-page limit.\nTo continue, re-run with the same filters:\n  {cmd}",
        fg=typer.colors.YELLOW,
        err=True,
    )


def _do_list(
    client,
    path: str,
    resource: str,
    *,
    limit: int,
    offset: int,
    all_pages: bool,
    output: str,
    resume_flags: Mapping[str, ResumeFlag] = _FILTER_CLI_FLAGS,
    **filters,
) -> None:
    """Shared list logic for all resources."""
    params = _build_filter_params(**filters)
    next_offset = None
    if all_pages:
        data = client.paginate(f"/{path}/", params=params, start_offset=offset)
        next_offset = data.pop("next_offset", None)
    else:
        params.update({"limit": limit, "offset": offset})
        data = client.get(f"/{path}/", params=params)
    format_output(data, resource=resource, fmt=output)
    # After the table so the resume hint is visible without scrolling up.
    if next_offset is not None:
        _warn_all_truncated(
            path,
            fetched_through=next_offset,
            total=data.get("count", next_offset),
            next_offset=next_offset,
            filters=filters,
            flags=resume_flags,
        )


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
    *,
    has_get: bool = True,
    has_create: bool = True,
    has_update: bool = True,
    has_delete: bool = False,
    has_number: bool = False,
    has_post: bool = False,
    filters: set[str],
    status_param: str = "record_status",
    template: dict | None = None,
    checks: list[Callable] | None = None,
    online_checks: list[Callable] | None = None,
) -> typer.Typer:
    """
    Create a Typer app for a standard CRUD resource.

    `filters` lists the flags this resource's v2 list endpoint declares; the rest
    are removed from `list` so the API cannot silently drop them.
    """
    import inspect

    app = typer.Typer(help=f"Manage {name}", no_args_is_help=True, cls=HelpfulGroup)
    unknown = filters - ALL_FILTERS
    if unknown:
        msg = f"{name}: unknown filter flags {sorted(unknown)}"
        raise ValueError(msg)
    remove = ALL_FILTERS - filters

    gated_options = {option for flag in remove for option in FILTER_OPTIONS[flag]}
    offered_options = sorted(FILTER_OPTIONS[flag][0] for flag in filters)

    @app.command("list", cls=make_list_command_cls(name, offered_options, gated_options))
    def list_cmd(
        *,
        limit: int = Limit,
        offset: int = Offset,
        all_pages: bool = AllPages,
        search: str | None = Search,
        status: str | None = Status,
        start_date: str | None = StartDate,
        end_date: str | None = EndDate,
        company: str | None = typer.Option(None, "--company", "-c", help="Filter by company ID"),
        customer: str | None = typer.Option(None, "--customer", help="Filter by customer ID"),
        vendor: str | None = typer.Option(None, "--vendor", help="Filter by vendor ID"),
        output: str = Format,
    ):
        from dualentry_cli.main import get_client

        client = get_client()
        _do_list(
            client,
            path,
            resource,
            limit=limit,
            offset=offset,
            all_pages=all_pages,
            output=output,
            search=_supplied(search),
            status=_supplied(status),
            start_date=_supplied(start_date),
            end_date=_supplied(end_date),
            status_param=status_param,
            company_id=_supplied(company),
            customer_id=_supplied(customer),
            vendor_id=_supplied(vendor),
        )

    list_cmd.__doc__ = f"List {name}."

    if remove:
        sig = inspect.signature(list_cmd)
        list_cmd.__signature__ = sig.replace(parameters=[p for p in sig.parameters.values() if p.name not in remove])

    if has_get and has_number:

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

    elif has_get and not has_number:

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

    if checks:

        @app.command("validate")
        def validate_cmd(
            file: Path = typer.Option(..., "--file", "-f", help="JSON file to validate"),
            online: bool = typer.Option(False, "--online", help="Also run checks that require API access"),
        ):
            payload = _load_json_file(file)
            errors: list[str] = []
            client = None
            if online:
                from dualentry_cli.main import get_client

                client = get_client()
            all_checks = list(checks)
            if online and online_checks:
                all_checks.extend(online_checks)
            for check in all_checks:
                if errors:
                    break
                errors.extend(check(payload, client=client))
            if errors:
                for err in errors:
                    typer.secho(f"  \u2717 {err}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=1)
            typer.secho("  \u2713 Valid", fg=typer.colors.GREEN)

        validate_cmd.__doc__ = f"Validate a {resource} payload."

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
