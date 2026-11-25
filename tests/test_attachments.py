"""`add-attachments` / `replace-attachments` on every resource whose v2 API accepts uploads."""

import json
import re
from unittest.mock import MagicMock, patch

import pytest
import typer.main
from typer.testing import CliRunner

from dualentry_cli.commands import ATTACHMENT_MAX_BYTES, make_resource_app
from dualentry_cli.main import app

runner = CliRunner()

# Every CLI resource whose /public/v2 router registers POST /{number}/attachments/.
ATTACHMENT_RESOURCES = [
    "invoices",
    "bills",
    "sales-orders",
    "customer-prepayments",
    "customer-prepayment-applications",
    "customer-deposits",
    "customer-refunds",
    "cash-sales",
    "purchase-orders",
    "vendor-payments",
    "vendor-refunds",
    "direct-expenses",
    "journal-entries",
    "statistical-journals",
]

# Transaction resources whose v2 router has no attachments route.
NO_ATTACHMENT_RESOURCES = ["customer-credits", "customer-payments", "vendor-credits", "vendor-prepayments", "vendor-prepayment-applications", "bank-transfers"]


# The shape the API returns for each attachment on the updated record.
_UPLOADED = {"id": 1, "file_name": "receipt.pdf", "file_size": 16, "download_url": "https://files.example.com/receipt.pdf"}


@pytest.fixture(autouse=True)
def mock_get_client():
    mock_client = MagicMock()
    mock_client.post.return_value = {"number": 7, "attachments": []}
    with patch("dualentry_cli.main.get_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def receipt(tmp_path):
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.7 receipt")
    return path


def _flat(output: str) -> str:
    """
    Undo rich's error-panel styling, so a message split across box lines still matches.

    Rich colors its output under CI (it detects GitHub Actions), wrapping every panel
    line in ANSI codes, so those go before the box borders and line breaks.
    """
    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    return " ".join(plain.replace("│", " ").split())


def _commands(resource: str) -> set[str]:
    return set(typer.main.get_command(app).commands[resource].commands)


class TestRegistration:
    @pytest.mark.parametrize("resource", ATTACHMENT_RESOURCES)
    def test_resource_with_upload_route_offers_add_attachments(self, resource):
        assert "add-attachments" in _commands(resource)

    @pytest.mark.parametrize("resource", NO_ATTACHMENT_RESOURCES)
    def test_resource_without_upload_route_has_no_attachment_commands(self, resource):
        assert not {"add-attachments", "replace-attachments"} & _commands(resource)

    def test_only_invoices_offer_replace_attachments(self):
        offering = {r for r in ATTACHMENT_RESOURCES if "replace-attachments" in _commands(r)}
        assert offering == {"invoices"}

    def test_attachments_without_record_numbers_are_rejected_at_registration(self):
        with pytest.raises(ValueError, match="has_attachments requires has_number"):
            make_resource_app("widgets", "widget", "widgets", has_attachments=True, filters=set())

    def test_replace_without_add_is_rejected_at_registration(self):
        with pytest.raises(ValueError, match="has_replace_attachments requires has_attachments"):
            make_resource_app("widgets", "widget", "widgets", has_replace_attachments=True, filters=set())


class TestAddAttachments:
    @pytest.mark.parametrize("resource", ATTACHMENT_RESOURCES)
    def test_posts_file_as_multipart_to_record_number(self, resource, receipt, mock_get_client):
        result = runner.invoke(app, [resource, "add-attachments", "7", "--file", str(receipt)])
        assert result.exit_code == 0, result.output
        mock_get_client.post.assert_called_once_with(
            f"/{resource}/7/attachments/",
            files=[("files", ("receipt.pdf", b"%PDF-1.7 receipt"))],
        )

    def test_repeated_file_flag_uploads_every_file_in_order(self, tmp_path, mock_get_client):
        first, second = tmp_path / "a.png", tmp_path / "b.csv"
        first.write_bytes(b"png")
        second.write_bytes(b"csv")
        result = runner.invoke(app, ["bills", "add-attachments", "3", "-f", str(first), "-f", str(second)])
        assert result.exit_code == 0, result.output
        _, kwargs = mock_get_client.post.call_args
        assert kwargs["files"] == [("files", ("a.png", b"png")), ("files", ("b.csv", b"csv"))]

    def test_json_output_prints_the_updated_record(self, receipt, mock_get_client):
        mock_get_client.post.return_value = {"number": 7, "attachments": [_UPLOADED]}
        result = runner.invoke(app, ["invoices", "add-attachments", "7", "-f", str(receipt), "-o", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output[result.output.index("{") :]) == mock_get_client.post.return_value

    def test_human_output_lists_the_record_attachments(self, receipt, mock_get_client):
        mock_get_client.post.return_value = {"number": 7, "attachments": [_UPLOADED, {**_UPLOADED, "id": 2, "file_name": "big.pdf", "file_size": 3_670_016}]}
        result = runner.invoke(app, ["invoices", "add-attachments", "7", "-f", str(receipt)])
        assert result.exit_code == 0, result.output
        out = _flat(result.output)
        assert "Attachments on invoice 7" in out
        assert "receipt.pdf" in out
        assert "16 B" in out
        assert "3.5 MiB" in out
        assert "2 attachments" in out


class TestReplaceAttachments:
    def test_posts_to_the_replace_route(self, receipt, mock_get_client):
        result = runner.invoke(app, ["invoices", "replace-attachments", "7", "--file", str(receipt)])
        assert result.exit_code == 0, result.output
        mock_get_client.post.assert_called_once_with(
            "/invoices/7/attachments/replace/",
            files=[("files", ("receipt.pdf", b"%PDF-1.7 receipt"))],
        )

    def test_help_warns_that_existing_attachments_are_deleted(self):
        result = runner.invoke(app, ["invoices", "replace-attachments", "--help"])
        assert "current attachments are deleted" in _flat(result.output)


class TestRejectedBeforeAnyUpload:
    @pytest.mark.parametrize("value", ["IN-42", "in-42", "42a", "4 2", "", "²", "٤٢"])
    def test_record_argument_must_be_a_plain_number(self, value, receipt, mock_get_client):
        result = runner.invoke(app, ["invoices", "add-attachments", value, "--file", str(receipt)])
        assert result.exit_code == 2
        assert "record number" in _flat(result.output)
        mock_get_client.post.assert_not_called()

    def test_negative_number_is_read_as_an_unknown_option(self, receipt, mock_get_client):
        result = runner.invoke(app, ["invoices", "add-attachments", "-1", "--file", str(receipt)])
        assert result.exit_code == 2
        mock_get_client.post.assert_not_called()

    def test_prefixed_id_error_names_the_resource_prefix(self, receipt):
        result = runner.invoke(app, ["invoices", "add-attachments", "IN-42", "--file", str(receipt)])
        assert "(not the IN-… ID)" in _flat(result.output)

    def test_empty_file(self, tmp_path, mock_get_client):
        empty = tmp_path / "empty.pdf"
        empty.touch()
        result = runner.invoke(app, ["bills", "add-attachments", "3", "--file", str(empty)])
        assert result.exit_code == 2
        assert "is empty" in _flat(result.output)
        mock_get_client.post.assert_not_called()

    def test_oversized_file_after_a_valid_one_sends_nothing(self, receipt, tmp_path, mock_get_client):
        big = tmp_path / "scan.tiff"
        with big.open("wb") as fh:
            fh.truncate(ATTACHMENT_MAX_BYTES + 1)
        result = runner.invoke(app, ["bills", "add-attachments", "3", "-f", str(receipt), "-f", str(big)])
        assert result.exit_code == 2
        assert "over the 10 MiB limit" in _flat(result.output)
        mock_get_client.post.assert_not_called()

    def test_file_at_exactly_the_limit_is_accepted(self, tmp_path, mock_get_client):
        edge = tmp_path / "edge.bin"
        with edge.open("wb") as fh:
            fh.truncate(ATTACHMENT_MAX_BYTES)
        result = runner.invoke(app, ["bills", "add-attachments", "3", "-f", str(edge)])
        assert result.exit_code == 0, result.output
        mock_get_client.post.assert_called_once()

    def test_missing_file(self, tmp_path, mock_get_client):
        result = runner.invoke(app, ["bills", "add-attachments", "3", "--file", str(tmp_path / "nope.pdf")])
        assert result.exit_code == 2
        mock_get_client.post.assert_not_called()

    def test_directory_is_not_a_file(self, tmp_path, mock_get_client):
        result = runner.invoke(app, ["bills", "add-attachments", "3", "--file", str(tmp_path)])
        assert result.exit_code == 2
        mock_get_client.post.assert_not_called()

    def test_file_flag_is_required(self, mock_get_client):
        result = runner.invoke(app, ["bills", "add-attachments", "3"])
        assert result.exit_code == 2
        mock_get_client.post.assert_not_called()


class TestStatisticalJournalPrefix:
    """`SJ-3` wraps the record number (unlike `IN-42`), so it is accepted and stripped."""

    @pytest.mark.parametrize("value", ["3", "SJ-3", "sj-3"])
    def test_number_or_prefixed_number_uploads_to_that_number(self, value, receipt, mock_get_client):
        result = runner.invoke(app, ["statistical-journals", "add-attachments", value, "-f", str(receipt)])
        assert result.exit_code == 0, result.output
        args, _ = mock_get_client.post.call_args
        assert args[0] == "/statistical-journals/3/attachments/"

    @pytest.mark.parametrize("value", ["IN-3", "SJ-", "SJ-x"])
    def test_other_prefixes_are_rejected(self, value, receipt, mock_get_client):
        result = runner.invoke(app, ["statistical-journals", "add-attachments", value, "-f", str(receipt)])
        assert result.exit_code == 2
        assert "such as 3 or SJ-3" in _flat(result.output)
        mock_get_client.post.assert_not_called()

    def test_oversized_file_is_now_rejected_here_too(self, tmp_path, mock_get_client):
        big = tmp_path / "scan.tiff"
        with big.open("wb") as fh:
            fh.truncate(ATTACHMENT_MAX_BYTES + 1)
        result = runner.invoke(app, ["statistical-journals", "add-attachments", "3", "-f", str(big)])
        assert result.exit_code == 2
        mock_get_client.post.assert_not_called()
