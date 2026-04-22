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


# ── Helpers ────────────────────────────────────────────────────────

_DRAFT_RESPONSE = {
    "internal_id": 200,
    "record_number": 55,
    "date": "2026-05-01",
    "transaction_date": "2026-05-01",
    "memo": "IC transfer",
    "currency_iso_4217_code": "USD",
    "exchange_rate": "1.00000000",
    "record_status": "draft",
    "companies": [{"id": 1, "name": "Alpha Co"}, {"id": 2, "name": "Beta Co"}],
    "company_ids": [1, 2],
    "items": [
        {
            "id": 10,
            "company_id": 1,
            "company_name": "Alpha Co",
            "account_number": 1000,
            "account_name": "Cash",
            "debit": "5000.00",
            "credit": "0.00",
            "memo": "",
            "position": 0,
            "eliminate": True,
        },
        {
            "id": 11,
            "company_id": 1,
            "company_name": "Alpha Co",
            "account_number": 2000,
            "account_name": "Payable",
            "debit": "0.00",
            "credit": "5000.00",
            "memo": "",
            "position": 1,
            "eliminate": True,
        },
        {
            "id": 12,
            "company_id": 2,
            "company_name": "Beta Co",
            "account_number": 1000,
            "account_name": "Cash",
            "debit": "5000.00",
            "credit": "0.00",
            "memo": "",
            "position": 2,
            "eliminate": True,
        },
        {
            "id": 13,
            "company_id": 2,
            "company_name": "Beta Co",
            "account_number": 2000,
            "account_name": "Payable",
            "debit": "0.00",
            "credit": "5000.00",
            "memo": "",
            "position": 3,
            "eliminate": True,
        },
    ],
}


def _valid_payload():
    return {
        "date": "2026-05-01",
        "memo": "IC transfer",
        "currency_iso_4217_code": "USD",
        "exchange_rate": "1.00000000",
        "record_status": "draft",
        "items": [
            {"company_id": 1, "account_number": 1000, "debit": "5000.00", "credit": "0.00", "memo": "", "position": 0, "eliminate": True},
            {"company_id": 1, "account_number": 2000, "debit": "0.00", "credit": "5000.00", "memo": "", "position": 1, "eliminate": True},
            {"company_id": 2, "account_number": 1000, "debit": "5000.00", "credit": "0.00", "memo": "", "position": 2, "eliminate": True},
            {"company_id": 2, "account_number": 2000, "debit": "0.00", "credit": "5000.00", "memo": "", "position": 3, "eliminate": True},
        ],
    }


# ── E2E workflow tests ─────────────────────────────────────────────


class TestIJEWorkflow:
    """Full workflow: template -> validate -> create -> list -> get -> post."""

    def test_template_validates_clean(self, tmp_path):
        tmpl = runner.invoke(app, ["intercompany-journal-entries", "template"])
        assert tmpl.exit_code == 0
        f = tmp_path / "ije.json"
        f.write_text(tmpl.output)
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_template_to_file_then_validate(self, tmp_path):
        f = tmp_path / "ije.json"
        runner.invoke(app, ["intercompany-journal-entries", "template", "--output", str(f)])
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 0

    def test_validate_then_create(self, mock_get_client, tmp_path):
        payload = _valid_payload()
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))

        val = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert val.exit_code == 0

        mock_get_client.post.return_value = {**_DRAFT_RESPONSE}
        create = runner.invoke(app, ["intercompany-journal-entries", "create", "--file", str(f)])
        assert create.exit_code == 0
        mock_get_client.post.assert_called_once_with("/intercompany-journal-entries/", json=payload)

    def test_create_then_get_then_post(self, mock_get_client, tmp_path):
        payload = _valid_payload()
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))

        mock_get_client.post.return_value = {**_DRAFT_RESPONSE}
        create = runner.invoke(app, ["intercompany-journal-entries", "create", "--file", str(f)])
        assert create.exit_code == 0

        mock_get_client.get.return_value = {**_DRAFT_RESPONSE}
        get = runner.invoke(app, ["intercompany-journal-entries", "get", "55"])
        assert get.exit_code == 0
        assert "IJE-200" in get.output
        assert "Alpha Co" in get.output
        assert "Beta Co" in get.output

        mock_get_client.get.return_value = {**_DRAFT_RESPONSE}
        mock_get_client.put.return_value = {**_DRAFT_RESPONSE, "record_status": "posted"}
        post = runner.invoke(app, ["intercompany-journal-entries", "post", "55"])
        assert post.exit_code == 0
        assert "POSTED" in post.output

        put_payload = mock_get_client.put.call_args[1]["json"]
        assert put_payload["record_status"] == "posted"
        assert "companies" not in put_payload
        assert "company_ids" not in put_payload
        assert "internal_id" not in put_payload
        for item in put_payload["items"]:
            assert "company_name" not in item
            assert "account_name" not in item

    def test_list_with_company_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["intercompany-journal-entries", "list", "--company", "42"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["company_id"] == "42"

    def test_list_with_status_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["intercompany-journal-entries", "list", "--status", "draft"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["record_status"] == "draft"

    def test_list_with_date_filters(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["intercompany-journal-entries", "list", "--start-date", "2026-01-01", "--end-date", "2026-12-31"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["start_date"] == "2026-01-01"
        assert call_params["end_date"] == "2026-12-31"

    def test_list_with_combined_filters(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(
            app,
            [
                "intercompany-journal-entries",
                "list",
                "--company",
                "7",
                "--status",
                "posted",
                "--start-date",
                "2026-01-01",
            ],
        )
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["company_id"] == "7"
        assert call_params["record_status"] == "posted"
        assert call_params["start_date"] == "2026-01-01"

    def test_list_without_filters_sends_no_extra_params(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["intercompany-journal-entries", "list"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert "company_id" not in call_params
        assert "customer_id" not in call_params
        assert "vendor_id" not in call_params

    def test_invoices_accept_customer_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--customer", "99"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["customer_id"] == "99"

    def test_invoices_accept_company_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--company", "5"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["company_id"] == "5"

    def test_invoices_reject_vendor_filter(self):
        result = runner.invoke(app, ["invoices", "list", "--vendor", "1"])
        assert result.exit_code != 0

    def test_bills_accept_vendor_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["bills", "list", "--vendor", "50"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["vendor_id"] == "50"

    def test_bills_accept_company_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["bills", "list", "--company", "3"])
        assert result.exit_code == 0
        call_params = mock_get_client.get.call_args[1]["params"]
        assert call_params["company_id"] == "3"

    def test_bills_reject_customer_filter(self):
        result = runner.invoke(app, ["bills", "list", "--customer", "1"])
        assert result.exit_code != 0

    def test_ije_accept_company_reject_others(self):
        result = runner.invoke(app, ["intercompany-journal-entries", "list", "--customer", "1"])
        assert result.exit_code != 0
        result = runner.invoke(app, ["intercompany-journal-entries", "list", "--vendor", "1"])
        assert result.exit_code != 0

    def test_json_output(self, mock_get_client):
        mock_get_client.get.return_value = {**_DRAFT_RESPONSE}
        result = runner.invoke(app, ["intercompany-journal-entries", "get", "55", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["internal_id"] == 200

    def test_get_by_prefix(self, mock_get_client):
        mock_get_client.get.return_value = {**_DRAFT_RESPONSE}
        result = runner.invoke(app, ["intercompany-journal-entries", "get", "IJE-55"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/intercompany-journal-entries/55/")


class TestIJEValidateComposition:
    """Validate command: check composition, short-circuit, --online."""

    def test_short_circuits_on_missing_items(self, tmp_path):
        f = tmp_path / "ije.json"
        f.write_text(json.dumps({"date": "2026-01-01"}))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 1
        assert "items" in result.output.lower()
        assert "debit" not in result.output.lower()
        assert "companies" not in result.output.lower()

    def test_short_circuits_on_invalid_amounts(self, tmp_path):
        payload = {
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "not-a-number", "credit": "0.00"},
                {"company_id": 2, "account_number": 2000, "debit": "0.00", "credit": "1000.00"},
            ],
        }
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 1
        assert "invalid" in result.output.lower()
        assert "companies" not in result.output.lower()

    def test_reports_balance_error(self, tmp_path):
        payload = {
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "1000.00", "credit": "0.00"},
                {"company_id": 2, "account_number": 2000, "debit": "0.00", "credit": "999.99"},
            ],
        }
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 1
        assert "1000.00" in result.output
        assert "999.99" in result.output

    def test_reports_single_company_error(self, tmp_path):
        payload = {
            "items": [
                {"company_id": 1, "account_number": 1000, "debit": "1000.00", "credit": "0.00"},
                {"company_id": 1, "account_number": 2000, "debit": "0.00", "credit": "1000.00"},
            ],
        }
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 1
        assert "two" in result.output.lower() or "companies" in result.output.lower()

    def test_online_checks_company_access(self, mock_get_client, tmp_path):
        mock_get_client.get.return_value = {"items": [{"id": 1}, {"id": 3}]}
        payload = _valid_payload()
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f), "--online"])
        assert result.exit_code == 1
        assert "2" in result.output
        assert "not accessible" in result.output.lower()

    def test_online_passes_when_all_companies_accessible(self, mock_get_client, tmp_path):
        mock_get_client.get.return_value = {"items": [{"id": 1}, {"id": 2}]}
        payload = _valid_payload()
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f), "--online"])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_offline_skips_company_access_check(self, mock_get_client, tmp_path):
        payload = _valid_payload()
        f = tmp_path / "ije.json"
        f.write_text(json.dumps(payload))
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 0
        mock_get_client.get.assert_not_called()

    def test_invalid_json_file(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", str(f)])
        assert result.exit_code == 1
        assert "invalid json" in result.output.lower() or "JSON" in result.output

    def test_missing_file(self):
        result = runner.invoke(app, ["intercompany-journal-entries", "validate", "--file", "/nonexistent/ije.json"])
        assert result.exit_code == 1
