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
        mock_get_client.get.return_value = {"items": [{"internal_id": 42, "number": 1, "total": "100.00"}], "count": 1}
        result = runner.invoke(app, ["invoices", "list"])
        assert result.exit_code == 0
        assert "IN-42" in result.output
        mock_get_client.get.assert_called_once_with("/invoices/", params={"limit": 20, "offset": 0})

    def test_invoices_list_with_pagination(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--limit", "50", "--offset", "10"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/invoices/", params={"limit": 50, "offset": 10})

    def test_invoices_list_json_output(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--format", "json"])
        assert result.exit_code == 0
        # Filter out update notification lines (if present) to get just the JSON
        output_lines = result.output.strip().split("\n")
        json_start = next(i for i, line in enumerate(output_lines) if line.strip().startswith("{"))
        json_output = "\n".join(output_lines[json_start:])
        parsed = json.loads(json_output)
        assert parsed == {"items": [], "count": 0}

    def test_invoices_get(self, mock_get_client):
        mock_get_client.get.return_value = {"internal_id": 42, "number": 1, "total": "100.00"}
        result = runner.invoke(app, ["invoices", "get", "1"])
        assert result.exit_code == 0
        assert "IN-42" in result.output
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


class TestJsonFileValidation:
    """Test JSON file loading and validation."""

    def test_load_json_file_not_found(self, tmp_path):
        from typer import Exit

        from dualentry_cli.commands import _load_json_file

        nonexistent = tmp_path / "nonexistent.json"
        with pytest.raises(Exit) as exc:
            _load_json_file(nonexistent)
        assert exc.value.exit_code == 1

    def test_load_json_file_invalid_json(self, tmp_path):
        from typer import Exit

        from dualentry_cli.commands import _load_json_file

        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{ this is not valid json }")
        with pytest.raises(Exit) as exc:
            _load_json_file(invalid_json)
        assert exc.value.exit_code == 1

    def test_load_json_file_valid(self, tmp_path):
        from dualentry_cli.commands import _load_json_file

        valid_json = tmp_path / "valid.json"
        valid_json.write_text('{"customer_id": 1, "amount": "100.00"}')
        data = _load_json_file(valid_json)
        assert data == {"customer_id": 1, "amount": "100.00"}

    @pytest.mark.usefixtures("mock_get_client")
    def test_create_with_invalid_json_file(self, tmp_path):
        """Test that create command shows helpful error for invalid JSON."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("not valid json")
        result = runner.invoke(app, ["invoices", "create", "--file", str(invalid_json)])
        assert result.exit_code == 1
        assert "Invalid JSON" in result.output or "Error" in result.output

    @pytest.mark.usefixtures("mock_get_client")
    def test_create_with_missing_file(self, tmp_path):
        """Test that create command shows helpful error for missing file."""
        result = runner.invoke(app, ["invoices", "create", "--file", str(tmp_path / "missing.json")])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "Error" in result.output
