"""DualEntry CLI entry point."""
import typer

app = typer.Typer(name="dualentry", help="DualEntry accounting CLI", no_args_is_help=True)

def version_callback(value: bool):
    if value:
        from dualentry_cli import __version__
        typer.echo(f"dualentry-cli {__version__}")
        raise typer.Exit

@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit.", callback=version_callback, is_eager=True),
):
    """DualEntry accounting CLI."""

if __name__ == "__main__":
    app()
