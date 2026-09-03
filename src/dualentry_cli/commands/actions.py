"""Helpers for custom API action commands."""

from __future__ import annotations

from pathlib import Path

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import Format, _do_list, _load_json_file
from dualentry_cli.output import format_output


def make_action_app(help: str) -> typer.Typer:
    return typer.Typer(help=help, no_args_is_help=True, cls=HelpfulGroup)


def run_get(path: str, *, resource: str, output: str, params: dict | None = None) -> None:
    from dualentry_cli.main import get_client

    data = get_client().get(path, params=params)
    format_output(data, resource=resource, fmt=output)


def run_list(path: str, *, resource: str, limit: int, offset: int, all_pages: bool, output: str, **filters) -> None:
    from dualentry_cli.main import get_client

    _do_list(get_client(), path.strip("/"), resource, limit=limit, offset=offset, all_pages=all_pages, output=output, **filters)


def run_post(path: str, *, resource: str, output: str, body: dict | None = None) -> None:
    from dualentry_cli.main import get_client

    data = get_client().post(path, json=body)
    format_output(data, resource=resource, fmt=output)


def load_json_file(file: Path) -> dict:
    return _load_json_file(file)


__all__ = ["Format", "load_json_file", "make_action_app", "run_get", "run_list", "run_post"]
