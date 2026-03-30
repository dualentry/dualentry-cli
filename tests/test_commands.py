import json
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner
from dualentry_cli.main import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def mock_get_client():
    mock_client = MagicMock()
    with patch("dualentry_cli.main.get_client", return_value=mock_client):
        yield mock_client

class TestInvoiceCommands:
    def test_invoices_list(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [{"id": 1, "number": "INV-001", "total": "100.00"}], "count": 1}
        result = runner.invoke(app, ["invoices", "list"])
        assert result.exit_code == 0
        assert "INV-001" in result.output
        mock_get_client.get.assert_called_once_with("/invoices/", params={"limit": 20, "offset": 0})

    def test_invoices_list_with_pagination(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--limit", "50", "--offset", "10"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/invoices/", params={"limit": 50, "offset": 10})

    def test_invoices_list_json_output(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--output", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed == {"items": [], "count": 0}

    def test_invoices_get(self, mock_get_client):
        mock_get_client.get.return_value = {"id": 1, "number": "INV-001", "total": "100.00"}
        result = runner.invoke(app, ["invoices", "get", "1"])
        assert result.exit_code == 0
        assert "INV-001" in result.output
        mock_get_client.get.assert_called_once_with("/invoices/1/")

    def test_invoices_create(self, mock_get_client, tmp_path):
        invoice_data = {"customer_id": 1, "lines": []}
        data_file = tmp_path / "invoice.json"
        data_file.write_text(json.dumps(invoice_data))
        mock_get_client.post.return_value = {"id": 1, "number": "INV-001"}
        result = runner.invoke(app, ["invoices", "create", "--file", str(data_file)])
        assert result.exit_code == 0
        mock_get_client.post.assert_called_once_with("/invoices/", json=invoice_data)

class TestBillCommands:
    def test_bills_list(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["bills", "list"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/bills/", params={"limit": 20, "offset": 0})

class TestAccountCommands:
    def test_accounts_list(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["accounts", "list"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/accounts/", params={"limit": 20, "offset": 0})

    def test_accounts_get(self, mock_get_client):
        mock_get_client.get.return_value = {"id": 1, "name": "Cash", "number": "1000"}
        result = runner.invoke(app, ["accounts", "get", "1"])
        assert result.exit_code == 0
        assert "Cash" in result.output
