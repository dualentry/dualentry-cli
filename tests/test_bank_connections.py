import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dualentry_cli.main import app

runner = CliRunner()


def test_list_connections():
    client = MagicMock()
    client.get.return_value = {"items": [], "count": 0}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(
            app,
            ["bank-connections", "list", "--updated-after", "2026-01-01T00:00:00"],
        )
    assert result.exit_code == 0
    client.get.assert_called_once_with(
        "/bank-connections/",
        params={"limit": 20, "offset": 0, "updated_after": "2026-01-01T00:00:00"},
    )


def test_get_connection():
    client = MagicMock()
    client.get.return_value = {"id": 42, "connection_source_id": "conn-1"}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-connections", "get", "42"])
    assert result.exit_code == 0
    client.get.assert_called_once_with("/bank-connections/42/", params=None)


def test_create_connection(tmp_path):
    payload = {
        "connection_source_id": "conn-1",
        "institution_name": "Customer Bank",
        "accounts": [{"account_id": "acct-1", "account_name": "Checking"}],
    }
    file = tmp_path / "connection.json"
    file.write_text(json.dumps(payload))
    client = MagicMock()
    client.post.return_value = {"id": 1, **payload}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-connections", "create", "--file", str(file)])
    assert result.exit_code == 0
    client.post.assert_called_once_with("/bank-connections/", json=payload)


def test_create_requires_file():
    with patch("dualentry_cli.main.get_client", return_value=MagicMock()):
        result = runner.invoke(app, ["bank-connections", "create"])
    assert result.exit_code == 2


def test_delete_connection():
    client = MagicMock()
    client.delete.return_value = {"success": True, "errors": {}}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-connections", "delete", "42"])
    assert result.exit_code == 0
    client.delete.assert_called_once_with("/bank-connections/42/")
    assert "Bank connection 42 deleted." in result.output


def test_accounts_list():
    client = MagicMock()
    client.get.return_value = [{"id": 1, "account_id": "acct-1", "account_name": "Checking"}]
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-connections", "accounts", "list", "42", "--format", "json"])
    assert result.exit_code == 0
    client.get.assert_called_once_with("/bank-connections/42/accounts/")
    parsed = json.loads(result.output)
    assert parsed["count"] == 1
    assert parsed["items"][0]["account_id"] == "acct-1"


def test_accounts_create(tmp_path):
    payload = {"accounts": [{"account_id": "acct-2", "account_name": "Savings"}]}
    file = tmp_path / "accounts.json"
    file.write_text(json.dumps(payload))
    client = MagicMock()
    client.post.return_value = {"id": 42, "accounts": payload["accounts"]}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(
            app,
            ["bank-connections", "accounts", "create", "42", "--file", str(file)],
        )
    assert result.exit_code == 0
    client.post.assert_called_once_with("/bank-connections/42/accounts/", json=payload)


def test_transactions_push(tmp_path):
    payload = {
        "transactions": [
            {
                "external_trx_id": "tx-1",
                "account_id": "acct-1",
                "date": "2026-01-15T00:00:00",
                "amount": "10.00",
                "description": "Deposit",
                "is_posted": True,
            }
        ]
    }
    file = tmp_path / "transactions.json"
    file.write_text(json.dumps(payload))
    client = MagicMock()
    client.post.return_value = {"success": True, "results": [{"external_trx_id": "tx-1", "status": "created"}]}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(
            app,
            ["bank-connections", "transactions", "push", "99", "--file", str(file)],
        )
    assert result.exit_code == 0
    client.post.assert_called_once_with(
        "/bank-connections/accounts/99/transactions/",
        json=payload,
    )


def test_template_connection_stdout():
    result = runner.invoke(app, ["bank-connections", "template", "--type", "connection"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["connection_source_id"] == "conn-1"
    assert parsed["institution_name"] == "Customer Bank"
    assert isinstance(parsed["accounts"], list)


def test_template_accounts_to_file(tmp_path):
    out_file = tmp_path / "accounts.json"
    result = runner.invoke(
        app,
        ["bank-connections", "template", "--type", "accounts", "--output", str(out_file)],
    )
    assert result.exit_code == 0
    assert out_file.exists()
    parsed = json.loads(out_file.read_text())
    assert "accounts" in parsed
    assert parsed["accounts"][0]["account_id"] == "acct-checking"


def test_template_transactions_stdout():
    result = runner.invoke(app, ["bank-connections", "template", "--type", "transactions"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "transactions" in parsed
    assert parsed["transactions"][0]["external_trx_id"] == "tx-1"


def test_template_unknown_type():
    result = runner.invoke(app, ["bank-connections", "template", "--type", "nope"])
    assert result.exit_code == 2
    assert "Unknown template type" in result.output
