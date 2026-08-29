"""Partial-update behaviour: `patch` merges, `update` warns before replacing."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from typer.testing import CliRunner

from dualentry_cli.client import APIError
from dualentry_cli.commands import PostWritableFields, _fields_cleared_by_put, _strip_to_writable
from dualentry_cli.main import app

runner = CliRunner()

POPULATED_INVOICE = {
    "internal_id": 42,
    "number": 1001,
    "created_at": "2026-01-01T00:00:00Z",
    "customer_id": 7,
    "company_id": 3,
    "due_date": "2026-03-01",
    "currency_iso_4217_code": "USD",
    "exchange_rate": "1.00000000",
    "memo": "Original memo",
    "reference_number": "REF-9",
    "term_id": 5,
    "ar_account_id": 11,
    "sales_order_id": 88,
    "contract_id": 4,
    "contracted": True,
    "record_status": "posted",
    "attachments": [{"id": 1}],
    "items": [{"id": 1, "item_id": 2, "quantity": "3.0", "rate": "50.00", "position": 1, "memo": "line"}],
}


@pytest.fixture
def mock_get_client():
    mock_client = MagicMock()
    with patch("dualentry_cli.main.get_client", return_value=mock_client):
        yield mock_client


def _write(tmp_path, payload):
    data_file = tmp_path / "payload.json"
    data_file.write_text(json.dumps(payload))
    return str(data_file)


class TestPatchCommand:
    def test_patch_sends_only_supplied_fields(self, mock_get_client, tmp_path):
        payload = {"memo": "Patched memo", "reference_number": "REF-10"}
        mock_get_client.patch.return_value = {**POPULATED_INVOICE, **payload}

        result = runner.invoke(app, ["invoices", "patch", "1001", "--file", _write(tmp_path, payload)])

        assert result.exit_code == 0
        mock_get_client.patch.assert_called_once_with("/invoices/1001/", json=payload)
        mock_get_client.put.assert_not_called()

    def test_patch_available_on_every_v2_patch_resource(self):
        for resource in (
            "invoices",
            "bills",
            "customer-prepayments",
            "customer-prepayment-applications",
            "customer-credits",
            "customer-payments",
            "vendors",
            "classifications",
            "customers",
            "items",
            "fixed-assets",
            "contracts",
        ):
            result = runner.invoke(app, [resource, "patch", "--help"])
            assert result.exit_code == 0, f"{resource} has no patch command"

    def test_no_patch_command_where_api_lacks_patch(self):
        result = runner.invoke(app, ["journal-entries", "patch", "--help"])
        assert result.exit_code != 0


class TestPatchLeavesOmittedFieldsAlone:
    """AC: apply a two-field change to a fully populated record, everything else survives."""

    @respx.mock
    def test_two_field_patch_preserves_every_other_field(self, tmp_path, monkeypatch):
        change = {"memo": "Patched memo", "reference_number": "REF-10"}

        def merge(request):
            sent = json.loads(request.content)
            assert sent == change, "CLI must forward only the supplied fields"
            return httpx.Response(200, json={**POPULATED_INVOICE, **sent})

        respx.patch("https://api.dualentry.com/public/v2/invoices/1001/").mock(side_effect=merge)

        monkeypatch.setenv("DUALENTRY_API_URL", "https://api.dualentry.com")
        monkeypatch.setenv("X_API_KEY", "test_key")
        result = runner.invoke(app, ["invoices", "patch", "1001", "--file", _write(tmp_path, change), "-o", "json"])

        assert result.exit_code == 0, result.output
        returned = json.loads(result.output)
        assert returned["memo"] == "Patched memo"
        assert returned["reference_number"] == "REF-10"
        untouched = {k: v for k, v in POPULATED_INVOICE.items() if k not in change}
        for field, original in untouched.items():
            assert returned[field] == original, f"{field} changed"


class TestUpdateWarnsBeforeReplacing:
    def test_lists_populated_fields_the_file_omits(self, mock_get_client, tmp_path):
        mock_get_client.get.return_value = POPULATED_INVOICE
        mock_get_client.put.return_value = POPULATED_INVOICE

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, {"memo": "only memo"})])

        assert result.exit_code == 0
        assert "replaces the whole invoice" in result.output
        for field in ("reference_number", "term_id", "customer_id", "items"):
            assert field in result.output
        assert "Use 'patch' instead" in result.output

    def test_does_not_warn_about_server_managed_fields(self, mock_get_client, tmp_path):
        mock_get_client.get.return_value = POPULATED_INVOICE
        mock_get_client.put.return_value = POPULATED_INVOICE
        full_payload = {k: v for k, v in POPULATED_INVOICE.items() if k not in {"internal_id", "number", "created_at"}}

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, full_payload)])

        assert result.exit_code == 0
        assert "replaces the whole" not in result.output

    def test_warns_that_omitting_record_status_posts_a_draft(self, mock_get_client, tmp_path):
        draft = {**POPULATED_INVOICE, "record_status": "draft"}
        mock_get_client.get.return_value = draft
        mock_get_client.put.return_value = draft
        payload = {k: v for k, v in draft.items() if k not in {"internal_id", "number", "created_at", "record_status"}}

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, payload)])

        assert result.exit_code == 0
        assert "this will post the record" in result.output

    def test_still_sends_the_put(self, mock_get_client, tmp_path):
        payload = {"memo": "only memo"}
        mock_get_client.get.return_value = POPULATED_INVOICE
        mock_get_client.put.return_value = POPULATED_INVOICE

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, payload)])

        assert result.exit_code == 0
        mock_get_client.put.assert_called_once_with("/invoices/1001/", json=payload)

    @pytest.mark.parametrize(
        "failure",
        [
            APIError(403, "no read access"),
            httpx.ConnectError("connection refused"),
            httpx.ReadTimeout("timed out"),
        ],
        ids=["api_error", "connect_error", "timeout"],
    )
    def test_update_proceeds_when_the_record_cannot_be_read(self, mock_get_client, tmp_path, failure):
        payload = {"memo": "only memo"}
        mock_get_client.get.side_effect = failure
        mock_get_client.put.return_value = POPULATED_INVOICE

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, payload)])

        assert result.exit_code == 0
        mock_get_client.put.assert_called_once_with("/invoices/1001/", json=payload)


class TestUpdateConfirmation:
    def test_aborts_when_the_user_declines_at_a_terminal(self, mock_get_client, tmp_path, monkeypatch):
        mock_get_client.get.return_value = POPULATED_INVOICE
        monkeypatch.setattr("dualentry_cli.commands._is_interactive", lambda: True)

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, {"memo": "x"})], input="n\n")

        assert result.exit_code != 0
        mock_get_client.put.assert_not_called()

    def test_proceeds_when_the_user_accepts(self, mock_get_client, tmp_path, monkeypatch):
        mock_get_client.get.return_value = POPULATED_INVOICE
        mock_get_client.put.return_value = POPULATED_INVOICE
        monkeypatch.setattr("dualentry_cli.commands._is_interactive", lambda: True)

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, {"memo": "x"})], input="y\n")

        assert result.exit_code == 0
        mock_get_client.put.assert_called_once()

    def test_yes_skips_the_warning_and_its_extra_read(self, mock_get_client, tmp_path, monkeypatch):
        mock_get_client.put.return_value = POPULATED_INVOICE
        monkeypatch.setattr("dualentry_cli.commands._is_interactive", lambda: True)

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, {"memo": "x"}), "--yes"])

        assert result.exit_code == 0
        mock_get_client.get.assert_not_called()
        assert "replaces the whole invoice" not in result.output
        mock_get_client.put.assert_called_once()

    def test_non_interactive_run_warns_and_continues(self, mock_get_client, tmp_path):
        mock_get_client.get.return_value = POPULATED_INVOICE
        mock_get_client.put.return_value = POPULATED_INVOICE

        result = runner.invoke(app, ["invoices", "update", "1001", "--file", _write(tmp_path, {"memo": "x"})])

        assert result.exit_code == 0
        assert "replaces the whole invoice" in result.output
        mock_get_client.put.assert_called_once()


class TestFieldsClearedByPut:
    def test_reports_populated_omitted_fields_only(self):
        current = {"memo": "keep", "reference_number": "", "term_id": None, "items": [], "customer_id": 7}
        assert _fields_cleared_by_put(current, {"memo": "new"}) == ["customer_id"]

    def test_ignores_fields_present_in_the_payload(self):
        current = {"memo": "keep", "customer_id": 7}
        assert _fields_cleared_by_put(current, {"memo": "new", "customer_id": 7}) == []

    def test_zero_and_false_count_as_data(self):
        current = {"exchange_rate": 0, "contracted": False}
        assert _fields_cleared_by_put(current, {}) == ["contracted", "exchange_rate"]


class TestStripToWritableIsResourceAware:
    def test_uses_the_shape_it_is_given(self):
        writable = PostWritableFields(record=frozenset({"memo", "items"}), line=frozenset({"id", "debit"}))
        data = {"memo": "m", "internal_id": 9, "items": [{"id": 1, "debit": "5.00", "account_name": "Cash"}]}

        assert _strip_to_writable(data, writable) == {"memo": "m", "items": [{"id": 1, "debit": "5.00"}]}

    def test_a_different_resource_keeps_its_own_fields(self):
        writable = PostWritableFields(record=frozenset({"customer_id", "lines"}), line=frozenset({"item_id", "quantity", "rate"}), line_key="lines")
        data = {"customer_id": 7, "memo": "dropped", "lines": [{"item_id": 2, "quantity": "3", "rate": "50", "total": "150"}]}

        assert _strip_to_writable(data, writable) == {"customer_id": 7, "lines": [{"item_id": 2, "quantity": "3", "rate": "50"}]}

    def test_leaves_a_missing_line_collection_alone(self):
        writable = PostWritableFields(record=frozenset({"memo", "items"}), line=frozenset({"id"}))
        assert _strip_to_writable({"memo": "m"}, writable) == {"memo": "m"}


class TestPostStaysOptIn:
    def test_post_is_absent_without_a_declared_shape(self):
        result = runner.invoke(app, ["invoices", "post", "--help"])
        assert result.exit_code != 0

    def test_intercompany_journal_entries_still_post(self):
        result = runner.invoke(app, ["intercompany-journal-entries", "post", "--help"])
        assert result.exit_code == 0
