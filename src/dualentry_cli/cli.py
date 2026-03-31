"""Shared CLI utilities."""

import difflib

import click
from typer.core import TyperGroup

LOGO = r"""
 /$$$$$$$                      /$$ /$$$$$$$$             /$$
| $$__  $$                    | $$| $$_____/            | $$
| $$  \ $$ /$$   /$$  /$$$$$$ | $$| $$       /$$$$$$$  /$$$$$$    /$$$$$$  /$$   /$$
| $$  | $$| $$  | $$ |____  $$| $$| $$$$$   | $$__  $$|_  $$_/   /$$__  $$| $$  | $$
| $$  | $$| $$  | $$  /$$$$$$$| $$| $$__/   | $$  \ $$  | $$    | $$  \__/| $$  | $$
| $$  | $$| $$  | $$ /$$__  $$| $$| $$      | $$  | $$  | $$ /$$| $$      | $$  | $$
| $$$$$$$/|  $$$$$$/|  $$$$$$$| $$| $$$$$$$$| $$  | $$  |  $$$$/| $$      |  $$$$$$$
|_______/  \______/  \_______/|__/|________/|__/  |__/   \___/  |__/       \____  $$
                                                                           /$$  | $$
                                                                          |  $$$$$$/
                                                                           \______/
"""


class HelpfulGroup(TyperGroup):
    """Typer group that shows help + suggestions instead of 'No such command'."""

    def format_help(self, ctx, formatter):
        # Only show logo for the root command (dualentry --help)
        if ctx.parent is None:
            click.echo(LOGO)
        super().format_help(ctx, formatter)

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            cmd_name = args[0] if args else None
            if cmd_name:
                matches = difflib.get_close_matches(cmd_name, self.list_commands(ctx), n=3, cutoff=0.4)
                if matches:
                    hint = ", ".join(f"'{m}'" for m in matches)
                    click.echo(f"Unknown command '{cmd_name}'. Did you mean: {hint}?\n", err=True)
                else:
                    click.echo(f"Unknown command '{cmd_name}'.\n", err=True)
            click.echo(ctx.get_help())
            ctx.exit(2)
