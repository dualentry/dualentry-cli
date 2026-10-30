"""
Classification line commands (read-only list across every classification).

`/classifications-lines/` has no detail, create, or update route, so `list` is the
only command. It gets its own module, not the resource factory, because its filters
(IDs, a name match, an active flag) don't fit the factory's shared flag set.
"""

from __future__ import annotations

from typing import Annotated

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, Format, Limit, Offset, ResumeFlag, Search, csv_ints_option
from dualentry_cli.commands.actions import run_list

app = typer.Typer(help="List classification lines (the values each classification offers)", no_args_is_help=True, cls=HelpfulGroup)

# Every list filter, so the --all resume hint repeats all of them.
_RESUME_FLAGS: dict[str, ResumeFlag] = {
    "search": "--search",
    "classification_id": "--classification",
    "id": "--id",
    "name": "--name",
    "is_active": ("--active", "--inactive"),
}


@app.command("list")
def list_cmd(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    classification: Annotated[
        list[int] | None,
        csv_ints_option("--classification", help_text="Filter by classification ID(s), comma-separated"),
    ] = None,
    line_id: Annotated[
        list[int] | None,
        csv_ints_option("--id", help_text="Filter by classification line ID(s), comma-separated"),
    ] = None,
    name: str | None = typer.Option(None, "--name", help="Filter by line name (case-insensitive substring)"),
    active: bool | None = typer.Option(None, "--active/--inactive", help="Only active or only inactive lines [default: both]"),
    output: str = Format,
) -> None:
    """List classification lines across all classifications."""
    run_list(
        "classifications-lines",
        resource="classification-line",
        resume_flags=_RESUME_FLAGS,
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        search=search,
        classification_id=classification,
        id=line_id,
        name=name or None,  # `extra` filters are only dropped when None, so "" must not reach the API
        is_active=active,
    )
