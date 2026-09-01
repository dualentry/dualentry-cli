"""Shared CLI utilities."""

import difflib

import typer

# typer >= 0.26 vendors click; the parser raises the vendored exceptions.
from typer._click.exceptions import NoSuchOption, UsageError
from typer.core import TyperCommand, TyperGroup

LOGO = r"""
 /$$$$$$$                      /$$                       /$$
| $$__  $$                    | $$                      | $$
| $$  \ $$ /$$   /$$  /$$$$$$ | $$  /$$$$$$  /$$$$$$$  /$$$$$$    /$$$$$$  /$$   /$$
| $$  | $$| $$  | $$ |____  $$| $$ /$$__  $$| $$__  $$|_  $$_/   /$$__  $$| $$  | $$
| $$  | $$| $$  | $$  /$$$$$$$| $$| $$$$$$$$| $$  \ $$  | $$    | $$  \__/| $$  | $$
| $$  | $$| $$  | $$ /$$__  $$| $$| $$_____/| $$  | $$  | $$ /$$| $$      | $$  | $$
| $$$$$$$/|  $$$$$$/|  $$$$$$$| $$|  $$$$$$$| $$  | $$  |  $$$$/| $$      |  $$$$$$$
|_______/  \______/  \_______/|__/ \_______/|__/  |__/   \___/  |__/       \____  $$
                                                                           /$$  | $$
                                                                          |  $$$$$$/
                                                                           \______/
"""


def make_list_command_cls(name: str, offered_options: list[str], gated_options: set[str]) -> type[TyperCommand]:
    """Build a list-command class that names the resource when a gated filter flag is passed."""
    offered = ", ".join(offered_options) or "none"

    class ResourceListCommand(TyperCommand):
        def parse_args(self, ctx, args):
            try:
                return super().parse_args(ctx, args)
            except NoSuchOption as exc:
                if exc.option_name not in gated_options:
                    raise
                message = f"{name} does not support {exc.option_name}. Supported filters: {offered}."
                raise UsageError(message, ctx=ctx) from None

    return ResourceListCommand


class HelpfulGroup(TyperGroup):
    """Typer group that shows help + suggestions instead of 'No such command'."""

    def format_help(self, ctx, formatter):
        if ctx.parent is None:
            typer.echo(LOGO)
        super().format_help(ctx, formatter)

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except UsageError:
            cmd_name = args[0] if args else None
            if cmd_name:
                matches = difflib.get_close_matches(cmd_name, self.list_commands(ctx), n=3, cutoff=0.4)
                if matches:
                    hint = ", ".join(f"'{m}'" for m in matches)
                    typer.echo(f"Unknown command '{cmd_name}'. Did you mean: {hint}?\n", err=True)
                else:
                    typer.echo(f"Unknown command '{cmd_name}'.\n", err=True)
            typer.echo(ctx.get_help())
            ctx.exit(2)
