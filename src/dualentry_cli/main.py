"""DualEntry CLI entry point."""

import os

import typer

from dualentry_cli.auth import clear_credentials, load_api_key, run_login_flow, store_api_key
from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import make_resource_app
from dualentry_cli.commands.accounts import app as accounts_app
from dualentry_cli.commands.bills import app as bills_app
from dualentry_cli.commands.invoices import app as invoices_app
from dualentry_cli.config import Config

app = typer.Typer(name="dualentry", help="DualEntry accounting CLI", no_args_is_help=True, cls=HelpfulGroup)
auth_app = typer.Typer(help="Authentication commands", no_args_is_help=True, cls=HelpfulGroup)
config_app = typer.Typer(help="Configuration commands", no_args_is_help=True, cls=HelpfulGroup)
app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")

# Custom-formatted resources
app.add_typer(invoices_app, name="invoices")
app.add_typer(bills_app, name="bills")
app.add_typer(accounts_app, name="accounts")

# Money-in
app.add_typer(make_resource_app("sales orders", "sales-order", "sales-orders", has_number=True), name="sales-orders")
app.add_typer(make_resource_app("customer payments", "customer-payment", "customer-payments", has_number=True), name="customer-payments")
app.add_typer(make_resource_app("customer credits", "customer-credit", "customer-credits", has_number=True), name="customer-credits")
app.add_typer(make_resource_app("customer prepayments", "customer-prepayment", "customer-prepayments", has_number=True), name="customer-prepayments")
app.add_typer(
    make_resource_app("customer prepayment applications", "customer-prepayment-application", "customer-prepayment-applications", has_number=True),
    name="customer-prepayment-applications",
)
app.add_typer(make_resource_app("customer deposits", "customer-deposit", "customer-deposits", has_number=True), name="customer-deposits")
app.add_typer(make_resource_app("customer refunds", "customer-refund", "customer-refunds", has_number=True), name="customer-refunds")
app.add_typer(make_resource_app("cash sales", "cash-sale", "cash-sales", has_number=True), name="cash-sales")

# Money-out
app.add_typer(make_resource_app("purchase orders", "purchase-order", "purchase-orders", has_number=True), name="purchase-orders")
app.add_typer(make_resource_app("vendor payments", "vendor-payment", "vendor-payments", has_number=True), name="vendor-payments")
app.add_typer(make_resource_app("vendor credits", "vendor-credit", "vendor-credits", has_number=True), name="vendor-credits")
app.add_typer(make_resource_app("vendor prepayments", "vendor-prepayment", "vendor-prepayments", has_number=True), name="vendor-prepayments")
app.add_typer(
    make_resource_app("vendor prepayment applications", "vendor-prepayment-application", "vendor-prepayment-applications", has_number=True), name="vendor-prepayment-applications"
)
app.add_typer(make_resource_app("vendor refunds", "vendor-refund", "vendor-refunds", has_number=True), name="vendor-refunds")
app.add_typer(make_resource_app("direct expenses", "direct-expense", "direct-expenses", has_number=True), name="direct-expenses")

# Accounting
app.add_typer(make_resource_app("journal entries", "journal-entry", "journal-entries", has_number=True), name="journal-entries")
app.add_typer(make_resource_app("bank transfers", "bank-transfer", "bank-transfers", has_number=True), name="bank-transfers")
app.add_typer(make_resource_app("fixed assets", "fixed-asset", "fixed-assets", has_number=True), name="fixed-assets")
app.add_typer(make_resource_app("depreciation books", "depreciation-book", "depreciation-books"), name="depreciation-books")

# Entities
app.add_typer(make_resource_app("customers", "customer", "customers"), name="customers")
app.add_typer(make_resource_app("vendors", "vendor", "vendors"), name="vendors")
app.add_typer(make_resource_app("items", "item", "items"), name="items")
app.add_typer(make_resource_app("companies", "company", "companies"), name="companies")
app.add_typer(make_resource_app("classifications", "classification", "classifications"), name="classifications")

# Recurring
recurring_app = typer.Typer(help="Manage recurring records", no_args_is_help=True, cls=HelpfulGroup)
recurring_app.add_typer(make_resource_app("recurring invoices", "recurring-invoice", "recurring/invoices", has_delete=True), name="invoices")
recurring_app.add_typer(make_resource_app("recurring bills", "recurring-bill", "recurring/bills", has_delete=True), name="bills")
recurring_app.add_typer(make_resource_app("recurring journal entries", "recurring-journal-entry", "recurring/journal-entries", has_delete=True), name="journal-entries")
app.add_typer(recurring_app, name="recurring")

# Other
app.add_typer(make_resource_app("contracts", "contract", "contracts"), name="contracts")
app.add_typer(make_resource_app("budgets", "budget", "budgets"), name="budgets")
app.add_typer(make_resource_app("workflows", "workflow", "workflows", has_create=False, has_update=False), name="workflows")


def version_callback(value: bool):
    if value:
        from dualentry_cli import __version__

        typer.echo(f"dualentry-cli {__version__}")
        raise typer.Exit


@app.callback()
def main(version: bool = typer.Option(False, "--version", "-v", help="Show version and exit.", callback=version_callback, is_eager=True)):
    """DualEntry accounting CLI."""
    from dualentry_cli.updater import check_for_updates

    check_for_updates()


@auth_app.command()
def login(api_url: str = typer.Option(None, "--api-url", help="API base URL override")):
    """Log in to DualEntry via browser."""
    config = Config()
    url = api_url or config.api_url
    result = run_login_flow(api_url=url)
    store_api_key(result["api_key"])
    config.organization_id = result["organization_id"]
    config.user_email = result["user_email"]
    config.save()
    typer.echo(f"Logged in as {result['user_email']} (org {result['organization_id']}).")


@auth_app.command()
def logout():
    """Log out and clear stored credentials."""
    clear_credentials()
    typer.echo("Logged out.")


@auth_app.command()
def status():
    """Show current authentication status."""
    env_key = os.environ.get("X_API_KEY")
    if env_key:
        typer.echo("Authenticated via X_API_KEY environment variable")
        return
    api_key = load_api_key()
    if not api_key:
        typer.echo("Not logged in. Run: dualentry auth login")
        raise typer.Exit(code=1)
    config = Config()
    typer.echo(f"API URL: {config.api_url}")
    if config.user_email:
        typer.echo(f"User: {config.user_email}")
    if config.organization_id:
        typer.echo(f"Organization: {config.organization_id}")
    typer.echo("Authenticated via API key")


@config_app.command("show")
def config_show():
    """Show current configuration."""
    config = Config()
    typer.echo(f"API URL: {config.api_url}")
    typer.echo(f"Output format: {config.output}")
    if config.user_email:
        typer.echo(f"User: {config.user_email}")
    if config.organization_id:
        typer.echo(f"Organization: {config.organization_id}")


@config_app.command("set-url")
def config_set_url(url: str = typer.Argument(help="Custom API base URL")):
    """Set a custom API URL."""
    config = Config()
    config.api_url = url
    config.save()
    typer.echo(f"API URL set to {url}")


def get_client():
    """Get an authenticated DualEntryClient."""
    from dualentry_cli.client import DualEntryClient

    config = Config()
    env_key = os.environ.get("X_API_KEY")
    api_key = env_key or load_api_key()
    if not api_key:
        typer.echo("Not logged in. Run: dualentry auth login")
        raise typer.Exit(code=1)
    return DualEntryClient(api_url=config.api_url, api_key=api_key)


def main_entrypoint():
    """Entry point with error handling."""
    from dualentry_cli.client import APIError

    try:
        app()
    except APIError as e:
        typer.secho(f"Error: {e.detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    main_entrypoint()
