"""Each resource may only offer the filter flags its /public/v2 list endpoint declares."""

import re
from unittest.mock import MagicMock, patch

import pytest
import typer.main
from typer.testing import CliRunner

from dualentry_cli.main import app

runner = CliRunner()

TXN = {"search", "status", "start-date", "end-date", "company"}
TXN_CUSTOMER = TXN | {"customer"}
TXN_VENDOR = TXN | {"vendor"}
TXN_ALL_PARTIES = TXN | {"customer", "vendor"}

EXPECTED_FILTERS = {
    "invoices": TXN_CUSTOMER,
    "bills": TXN_VENDOR,
    "sales-orders": TXN_CUSTOMER,
    "customer-payments": TXN_CUSTOMER,
    "customer-credits": TXN_CUSTOMER,
    "customer-prepayments": TXN_CUSTOMER,
    "customer-prepayment-applications": TXN_CUSTOMER,
    "customer-deposits": TXN_CUSTOMER,
    "customer-refunds": TXN_CUSTOMER,
    "cash-sales": TXN_CUSTOMER,
    "purchase-orders": TXN_VENDOR,
    "vendor-payments": TXN_VENDOR,
    "vendor-credits": TXN_VENDOR,
    "vendor-prepayments": TXN_VENDOR,
    "vendor-prepayment-applications": TXN_VENDOR,
    "vendor-refunds": TXN_VENDOR,
    "direct-expenses": TXN_VENDOR,
    "journal-entries": TXN_ALL_PARTIES,
    "bank-transfers": TXN,
    "fixed-assets": {"search", "status", "company", "customer", "vendor"},
    "depreciation-books": set(),
    "customers": {"search", "status", "company"},
    "vendors": TXN,
    "items": {"search", "status"},
    "companies": {"search"},
    "classifications": {"search"},
    "recurring/invoices": {"search", "company"},
    "recurring/bills": {"search", "company"},
    "recurring/journal-entries": {"search", "company"},
    "contracts": TXN_CUSTOMER,
    "budgets": {"search", "status", "company"},
    "workflows": {"search", "company"},
    "intercompany-journal-entries": TXN,
    "paper-checks": TXN_ALL_PARTIES,
    "inbox": {"search"},
}

FILTER_FLAGS = {"search", "status", "start-date", "end-date", "company", "customer", "vendor"}


def _plain(text: str) -> str:
    """Strip the ANSI styling rich injects mid-token, so `--start-date` is greppable."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


@pytest.fixture(autouse=True)
def mock_get_client():
    mock_client = MagicMock()
    mock_client.get.return_value = {"items": [], "count": 0}
    with patch("dualentry_cli.main.get_client", return_value=mock_client):
        yield mock_client


def _offered_filters(path: str) -> set[str]:
    """Filter flags the `list` command of a resource actually exposes."""
    cmd = typer.main.get_command(app)
    for part in path.split("/"):
        cmd = cmd.commands[part]
    list_cmd = cmd.commands["list"]
    return {opt[2:] for p in list_cmd.params for opt in p.opts if opt.startswith("--") and opt[2:] in FILTER_FLAGS}


@pytest.mark.parametrize("path", sorted(EXPECTED_FILTERS))
def test_offers_only_supported_filters(path):
    assert _offered_filters(path) == EXPECTED_FILTERS[path]


class TestUnsupportedFlagsRejected:
    @pytest.mark.parametrize(
        ("path", "flag"),
        [
            ("customers", "--start-date"),
            ("customers", "--end-date"),
            ("items", "--start-date"),
            ("items", "--end-date"),
            ("companies", "--start-date"),
            ("companies", "--status"),
            ("budgets", "--start-date"),
            ("budgets", "--end-date"),
            ("depreciation-books", "--search"),
            ("classifications", "--status"),
            ("workflows", "--end-date"),
            ("inbox", "--status"),
        ],
    )
    def test_exits_non_zero_naming_flag_and_resource(self, path, flag, mock_get_client):
        result = runner.invoke(app, [path, "list", flag, "2025-01-01"])
        assert result.exit_code != 0
        output = _plain(result.output)
        assert f"does not support {flag}" in output
        assert f"dualentry {path.replace('/', ' ')} list" in output
        mock_get_client.get.assert_not_called()

    @pytest.mark.parametrize(("path", "alias"), [("companies", "-c"), ("depreciation-books", "-s"), ("items", "-c")])
    def test_short_aliases_are_gated_too(self, path, alias, mock_get_client):
        result = runner.invoke(app, [path, "list", alias, "x"])
        assert result.exit_code != 0
        assert f"does not support {alias}" in _plain(result.output)
        mock_get_client.get.assert_not_called()

    def test_recurring_rejects_status(self, mock_get_client):
        result = runner.invoke(app, ["recurring", "invoices", "list", "--status", "posted"])
        assert result.exit_code != 0
        assert "--status" in _plain(result.output)
        mock_get_client.get.assert_not_called()


class TestSupportedFiltersStillForwarded:
    def test_customers_status_is_sent(self, mock_get_client):
        result = runner.invoke(app, ["customers", "list", "--status", "posted"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/customers/", params={"record_status": "posted", "limit": 20, "offset": 0})

    def test_items_search_is_sent(self, mock_get_client):
        result = runner.invoke(app, ["items", "list", "--search", "widget"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/items/", params={"search": "widget", "limit": 20, "offset": 0})

    def test_invoices_accept_the_full_generic_set(self, mock_get_client):
        result = runner.invoke(
            app,
            ["invoices", "list", "--search", "acme", "--status", "posted", "--start-date", "2025-01-01", "--end-date", "2025-12-31"],
        )
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with(
            "/invoices/",
            params={
                "search": "acme",
                "record_status": "posted",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "limit": 20,
                "offset": 0,
            },
        )

    def test_customers_company_filter_is_now_offered(self, mock_get_client):
        result = runner.invoke(app, ["customers", "list", "--company", "7"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/customers/", params={"company_id": "7", "limit": 20, "offset": 0})


class TestStatusParamName:
    def test_contracts_status_maps_to_status_not_record_status(self, mock_get_client):
        result = runner.invoke(app, ["contracts", "list", "--status", "active"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/contracts/", params={"status": "active", "limit": 20, "offset": 0})

    def test_fixed_assets_status_stays_record_status(self, mock_get_client):
        result = runner.invoke(app, ["fixed-assets", "list", "--status", "posted"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/fixed-assets/", params={"record_status": "posted", "limit": 20, "offset": 0})


class TestFactoryGuards:
    def test_unknown_filter_flag_is_rejected_at_registration(self):
        from dualentry_cli.commands import make_resource_app

        with pytest.raises(ValueError, match="unknown filter flags"):
            make_resource_app("widgets", "widget", "widgets", filters={"nonsense"})

    def test_filters_argument_is_required(self):
        from dualentry_cli.commands import make_resource_app

        with pytest.raises(TypeError):
            make_resource_app("widgets", "widget", "widgets")
