import base64
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dualentry_cli.client import APIError
from dualentry_cli.main import app

runner = CliRunner()

QUOTE = {
    "id": 45,
    "number": 12,
    "approval_status": "approved",
    "customer_name": "Acme Example",
    "company_name": "Example Co",
    "currency_iso_4217_code": "USD",
    "contract_start_date": "2026-01-01",
    "contract_end_type": "after",
    "number_of_months": 12,
    "contract_end_date": "2026-12-31",
    "valid_until": "2025-12-31",
    "sent_at": None,
    "items": [
        {
            "item_name": "Setup",
            "billing_frequency": "one_time",
            "billing_interval": 1,
            "billing_start_date": "2026-01-01",
            "billing_end_date": "2026-01-01",
            "quantity": "1",
            "rate": "5000",
            "line_tcv": "5000.00",
        },
        {
            "item_name": "Seats",
            "billing_frequency": "monthly",
            "billing_interval": 1,
            "billing_start_date": "2026-01-01",
            "billing_end_date": "2026-12-31",
            "quantity": "10",
            "rate": "50",
            "line_tcv": "6000.00",
        },
    ],
    "recipients": [{"name": "Ana Diaz", "side": "buyer", "signing_order": 1}],
    "totals": {
        "one_time": {"total": "5000.00"},
        "recurring": [{"billing_frequency": "monthly", "billing_interval": 1, "total": "500.00"}],
        "mrr": "500.00",
        "arr": "6000.00",
        "first_invoice_amount": "5500.00",
        "tcv": "11000.00",
        "years": [{"year": 1, "total": "11000.00"}],
    },
}


def _invoke(args, client):
    with patch("dualentry_cli.main.get_client", return_value=client):
        return runner.invoke(app, args)


def test_list_passes_quote_filters():
    client = MagicMock()
    client.get.return_value = {"items": [QUOTE], "count": 1}

    result = _invoke(["quotes", "list", "--approval-status", "approved", "--customer", "7", "--valid-from", "2026-01-01", "--ordering", "-amount"], client)

    assert result.exit_code == 0, result.output
    client.get.assert_called_once_with(
        "/quotes/",
        params={"approval_status": "approved", "customer_id": "7", "valid_until_from": "2026-01-01", "ordering": "-amount", "limit": 20, "offset": 0},
    )
    assert "QT-45" in result.output


def test_get_by_number_shows_totals_and_signing_order():
    client = MagicMock()
    client.get.return_value = QUOTE

    result = _invoke(["quotes", "get", "12"], client)

    assert result.exit_code == 0, result.output
    client.get.assert_called_once_with("/quotes/12/")
    for text in ("MRR / ARR", "$11,000.00", "Year 1", "1. Ana Diaz"):
        assert text in result.output


def test_get_ongoing_quote_shows_ongoing_tcv():
    client = MagicMock()
    client.get.return_value = QUOTE | {"contract_end_type": "ongoing", "totals": QUOTE["totals"] | {"tcv": None, "years": []}}

    result = _invoke(["quotes", "get", "12"], client)

    assert result.exit_code == 0, result.output
    assert "Ongoing" in result.output


def test_get_by_qt_id_resolves_the_number():
    client = MagicMock()
    client.get.side_effect = [{"items": [QUOTE], "count": 1}, QUOTE]

    result = _invoke(["quotes", "get", "QT-45", "-o", "json"], client)

    assert result.exit_code == 0, result.output
    assert [c.args[0] for c in client.get.call_args_list] == ["/quotes/", "/quotes/12/"]
    assert client.get.call_args_list[0].kwargs["params"] == {"id": 45, "limit": 1}


def test_get_rejects_other_references():
    result = _invoke(["quotes", "get", "IN-12"], MagicMock())

    assert result.exit_code == 2
    assert "not a quote number" in result.output


def test_create_merges_display_options(tmp_path):
    file = tmp_path / "quote.json"
    file.write_text(json.dumps({"company_id": 1}))
    client = MagicMock()
    client.post.return_value = QUOTE

    result = _invoke(["quotes", "create", "-f", str(file), "--display-options", '{"headline_total": "annual", "year_by_year": true}', "-o", "json"], client)

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with("/quotes/", json={"company_id": 1, "document_headline_total": "annual", "document_year_by_year": True})


def test_display_options_reject_unknown_keys(tmp_path):
    file = tmp_path / "quote.json"
    file.write_text("{}")

    result = _invoke(["quotes", "create", "-f", str(file), "--display-options", '{"colour": "red"}'], MagicMock())

    assert result.exit_code == 2


def test_update_patches_only_sent_fields(tmp_path):
    file = tmp_path / "changes.json"
    file.write_text(json.dumps({"memo": "Renewal"}))
    client = MagicMock()
    client.patch.return_value = QUOTE

    result = _invoke(["quotes", "update", "12", "-f", str(file), "-o", "json"], client)

    assert result.exit_code == 0, result.output
    client.patch.assert_called_once_with("/quotes/12/", json={"memo": "Renewal"})


def test_update_needs_something_to_send():
    result = _invoke(["quotes", "update", "12"], MagicMock())

    assert result.exit_code == 2


def test_submit_posts_the_quote():
    client = MagicMock()
    client.patch.return_value = QUOTE | {"approval_status": "pending_approval"}

    result = _invoke(["quotes", "submit", "12"], client)

    assert result.exit_code == 0, result.output
    client.patch.assert_called_once_with("/quotes/12/", json={"record_status": "posted"})


def test_send_attaches_the_pdf(tmp_path):
    pdf = tmp_path / "quote.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    client = MagicMock()

    result = _invoke(["quotes", "send", "12", "--pdf", str(pdf), "--cc", "cc@example.com"], client)

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with(
        "/quotes/12/send/",
        json={"cc_emails": ["cc@example.com"], "attach_pdf": True, "pdf_content": base64.b64encode(b"%PDF-1.4").decode()},
    )


def test_send_without_pdf():
    client = MagicMock()

    result = _invoke(["quotes", "send", "12", "--no-pdf"], client)

    assert result.exit_code == 0, result.output
    client.post.assert_called_once_with("/quotes/12/send/", json={"attach_pdf": False})


def test_missing_subscription_is_a_clear_error():
    client = MagicMock()
    client.get.side_effect = APIError(402, "Subscription required for this feature")

    result = _invoke(["quotes", "list"], client)

    assert result.exit_code != 0
    assert isinstance(result.exception, APIError)
    assert result.exception.status_code == 402


def test_template_is_valid_json():
    result = runner.invoke(app, ["quotes", "template"])

    assert result.exit_code == 0
    assert json.loads(result.output)["items"][1]["billing_frequency"] == "monthly"
