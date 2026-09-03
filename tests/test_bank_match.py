import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dualentry_cli.main import app

runner = CliRunner()


def test_suggestions_list():
    client = MagicMock()
    client.get.return_value = {"items": [], "count": 0}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-match", "suggestions", "list", "--highest-ranked"])
    assert result.exit_code == 0
    client.get.assert_called_once_with(
        "/bank-match/suggestions/",
        params={"limit": 20, "offset": 0, "is_highest_ranked": True},
    )


def test_bank_transactions_list():
    client = MagicMock()
    client.get.return_value = {"items": [], "count": 0}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["bank-match", "bank-transactions", "list", "--matching-status", "matched"])
    assert result.exit_code == 0
    client.get.assert_called_once_with(
        "/bank-match/bank-transactions/",
        params={"limit": 20, "offset": 0, "matching_status": "matched"},
    )


def test_match_one_to_one():
    client = MagicMock()
    client.post.return_value = {"success": True, "errors": {}}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(
            app,
            ["bank-match", "match", "--financial-transaction-id", "10", "--transaction-id", "20"],
        )
    assert result.exit_code == 0
    client.post.assert_called_once_with(
        "/bank-match/matches/",
        json={"financial_transaction_id": 10, "transaction_id": 20},
    )


def test_unmatch_requires_one_identifier():
    with patch("dualentry_cli.main.get_client", return_value=MagicMock()):
        result = runner.invoke(app, ["bank-match", "unmatch"])
    assert result.exit_code == 2
    assert "provide exactly one" in result.output


def test_template_stdout():
    result = runner.invoke(app, ["bank-match", "template"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["financial_transaction_id"] == 10
    assert parsed["transaction_id"] == 20


def test_template_to_file(tmp_path):
    out_file = tmp_path / "template.json"
    result = runner.invoke(app, ["bank-match", "template", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    parsed = json.loads(out_file.read_text())
    assert parsed["financial_transaction_id"] == 10
    assert parsed["transaction_id"] == 20


def test_bank_match_has_no_crud_list():
    result = runner.invoke(app, ["bank-match", "list"])
    assert result.exit_code != 0
