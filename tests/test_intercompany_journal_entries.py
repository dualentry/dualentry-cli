import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dualentry_cli.main import app
from dualentry_cli.output import format_output

runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_get_client():
    mock_client = MagicMock()
    with patch("dualentry_cli.main.get_client", return_value=mock_client):
        yield mock_client


class TestIJEFormatting:
    def test_ije_list_shows_prefix(self, capsys):
        data = {
            "items": [
                {
                    "internal_id": 100,
                    "record_number": 42,
                    "date": "2026-04-20",
                    "memo": "IC transfer",
                    "currency_iso_4217_code": "USD",
                    "record_status": "posted",
                    "companies": [
                        {"id": 1, "name": "Company A"},
                        {"id": 2, "name": "Company B"},
                    ],
                    "items": [
                        {"debit": "1000.00", "credit": "0.00"},
                        {"debit": "0.00", "credit": "1000.00"},
                    ],
                }
            ],
            "count": 1,
        }
        format_output(data, resource="intercompany-journal-entry", fmt="human")
        captured = capsys.readouterr()
        assert "IJE-100" in captured.out
        assert "Company A" in captured.out
        assert "Company B" in captured.out
        assert "IC" in captured.out
        assert "transfer" in captured.out

    def test_ije_detail_shows_lines_with_company(self, capsys):
        data = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "transaction_date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "exchange_rate": "1.00000000",
            "record_status": "posted",
            "companies": [
                {"id": 1, "name": "Company A"},
                {"id": 2, "name": "Company B"},
            ],
            "items": [
                {
                    "id": 1,
                    "company_id": 1,
                    "company_name": "Company A",
                    "account_number": 1000,
                    "account_name": "Cash",
                    "debit": "1000.00",
                    "credit": "0.00",
                    "memo": "Debit line",
                    "position": 0,
                    "eliminate": True,
                },
                {
                    "id": 2,
                    "company_id": 2,
                    "company_name": "Company B",
                    "account_number": 2000,
                    "account_name": "Payable",
                    "debit": "0.00",
                    "credit": "1000.00",
                    "memo": "Credit line",
                    "position": 1,
                    "eliminate": False,
                },
            ],
        }
        format_output(data, resource="intercompany-journal-entry", fmt="human")
        captured = capsys.readouterr()
        assert "INTERCOMPANY JOURNAL ENTRY" in captured.out
        assert "IJE-100" in captured.out
        assert "Company A" in captured.out
        assert "Company B" in captured.out
        assert "Cash" in captured.out
        assert "Payable" in captured.out


class TestIJECommands:
    def test_list(self, mock_get_client):
        mock_get_client.get.return_value = {
            "items": [
                {
                    "internal_id": 100,
                    "record_number": 42,
                    "date": "2026-04-20",
                    "memo": "IC transfer",
                    "currency_iso_4217_code": "USD",
                    "record_status": "posted",
                    "companies": [{"id": 1, "name": "Co A"}, {"id": 2, "name": "Co B"}],
                    "items": [{"debit": "1000.00", "credit": "0.00"}, {"debit": "0.00", "credit": "1000.00"}],
                }
            ],
            "count": 1,
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "list"])
        assert result.exit_code == 0
        assert "IJE-100" in result.output
        mock_get_client.get.assert_called_once_with("/intercompany-journal-entries/", params={"limit": 20, "offset": 0})

    def test_get_by_number(self, mock_get_client):
        mock_get_client.get.return_value = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "record_status": "posted",
            "companies": [],
            "items": [],
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "get", "42"])
        assert result.exit_code == 0
        assert "IJE-100" in result.output
        mock_get_client.get.assert_called_once_with("/intercompany-journal-entries/42/")

    def test_create(self, mock_get_client, tmp_path):
        payload = {"date": "2026-04-20", "memo": "test", "items": []}
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        mock_get_client.post.return_value = {
            "internal_id": 101,
            "record_number": 43,
            "date": "2026-04-20",
            "memo": "test",
            "currency_iso_4217_code": "USD",
            "record_status": "draft",
            "companies": [],
            "items": [],
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "create", "--file", str(data_file)])
        assert result.exit_code == 0
        mock_get_client.post.assert_called_once_with("/intercompany-journal-entries/", json=payload)

    def test_update(self, mock_get_client, tmp_path):
        payload = {"memo": "updated"}
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        mock_get_client.put.return_value = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "memo": "updated",
            "currency_iso_4217_code": "USD",
            "record_status": "draft",
            "companies": [],
            "items": [],
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "update", "42", "--file", str(data_file)])
        assert result.exit_code == 0
        mock_get_client.put.assert_called_once_with("/intercompany-journal-entries/42/", json=payload)


class TestIJEValidate:
    def test_validate_valid_payload(self, tmp_path):
        payload = {
            "date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "1000.00", "credit": "0.00"},
                {"company_id": 2, "account_number": 2000, "debit": "0.00", "credit": "1000.00"},
            ],
        }
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(data_file)])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_validate_unbalanced(self, tmp_path):
        payload = {
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "1000.00", "credit": "0.00"},
                {"company_id": 2, "account_number": 2000, "debit": "0.00", "credit": "500.00"},
            ],
        }
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(data_file)])
        assert result.exit_code == 1
        assert "debit" in result.output.lower() or "balance" in result.output.lower()

    def test_validate_single_company(self, tmp_path):
        payload = {
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "1000.00", "credit": "0.00"},
                {"company_id": 1, "account_number": 2000, "debit": "0.00", "credit": "1000.00"},
            ],
        }
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(data_file)])
        assert result.exit_code == 1
        assert "two" in result.output.lower() or "companies" in result.output.lower()

    def test_validate_missing_items(self, tmp_path):
        payload = {"date": "2026-04-20", "memo": "IC transfer"}
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(data_file)])
        assert result.exit_code == 1
        assert "items" in result.output.lower()

    def test_validate_empty_items(self, tmp_path):
        payload = {"items": []}
        data_file = tmp_path / "ije.json"
        data_file.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(data_file)])
        assert result.exit_code == 1


class TestIJEPost:
    def test_post_draft_to_posted(self, mock_get_client):
        draft_response = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "transaction_date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "exchange_rate": "1.00000000",
            "record_status": "draft",
            "companies": [{"id": 1, "name": "Co A"}, {"id": 2, "name": "Co B"}, {"id": 3, "name": "Elim Co"}],
            "company_ids": [1, 2, 3],
            "items": [
                {"id": 1, "company_id": 1, "company_name": "Co A", "account_number": 1000, "debit": "1000.00", "credit": "0.00", "memo": "", "position": 0, "eliminate": True},
                {"id": 2, "company_id": 2, "company_name": "Co B", "account_number": 2000, "debit": "0.00", "credit": "1000.00", "memo": "", "position": 1, "eliminate": True},
                {"id": 3, "company_id": 3, "company_name": "Elim Co", "account_number": 1000, "debit": "0.00", "credit": "1000.00", "memo": "", "position": 2, "eliminate": True},
                {"id": 4, "company_id": 3, "company_name": "Elim Co", "account_number": 2000, "debit": "1000.00", "credit": "0.00", "memo": "", "position": 3, "eliminate": True},
            ],
        }
        posted_response = {**draft_response, "record_status": "posted"}
        mock_get_client.get.return_value = draft_response
        mock_get_client.put.return_value = posted_response
        result = runner.invoke(app, ["intercompany-journal-entries", "post", "42"])
        assert result.exit_code == 0
        assert "POSTED" in result.output
        put_call = mock_get_client.put.call_args
        assert put_call[0][0] == "/intercompany-journal-entries/42/"
        put_payload = put_call[1]["json"]
        assert put_payload["record_status"] == "posted"
        assert "companies" not in put_payload
        assert "company_ids" not in put_payload
        assert "record_number" not in put_payload
        assert "internal_id" not in put_payload
        assert "company_name" not in put_payload["items"][0]

    def test_post_already_posted_fails(self, mock_get_client):
        mock_get_client.get.return_value = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "record_status": "posted",
            "companies": [],
            "items": [],
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "post", "42"])
        assert result.exit_code == 1
        assert "already" in result.output.lower() or "draft" in result.output.lower()

    def test_post_archived_fails(self, mock_get_client):
        mock_get_client.get.return_value = {
            "internal_id": 100,
            "record_number": 42,
            "date": "2026-04-20",
            "memo": "IC transfer",
            "currency_iso_4217_code": "USD",
            "record_status": "archived",
            "companies": [],
            "items": [],
        }
        result = runner.invoke(app, ["intercompany-journal-entries", "post", "42"])
        assert result.exit_code == 1


class TestIJETemplate:
    def test_template_stdout(self):
        result = runner.invoke(app, ["intercompany-journal-entries", "template"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "date" in parsed
        assert "items" in parsed
        assert len(parsed["items"]) == 4
        company_ids = {item["company_id"] for item in parsed["items"]}
        assert len(company_ids) >= 2
        assert parsed["record_status"] == "draft"

    def test_template_to_file(self, tmp_path):
        out_file = tmp_path / "template.json"
        result = runner.invoke(app, ["intercompany-journal-entries", "template", "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        parsed = json.loads(out_file.read_text())
        assert "items" in parsed
        assert len(parsed["items"]) == 4

    def test_template_is_balanced(self):
        result = runner.invoke(app, ["intercompany-journal-entries", "template"])
        parsed = json.loads(result.output)
        total_debits = sum(float(item["debit"]) for item in parsed["items"])
        total_credits = sum(float(item["credit"]) for item in parsed["items"])
        assert total_debits == total_credits
