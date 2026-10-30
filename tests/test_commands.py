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


class TestErrorHandling:
    """Test that API errors produce clean output without tracebacks."""

    def test_api_error_caught_by_runner(self, mock_get_client):
        from dualentry_cli.client import APIError

        mock_get_client.get.side_effect = APIError(404, "Resource not found. Check the ID or number and try again.")
        result = runner.invoke(app, ["journal-entries", "get", "99999"])
        assert result.exit_code == 1

    def test_main_entrypoint_catches_api_error(self, mock_get_client, monkeypatch, capsys):
        """The real entrypoint prints the error and exits without traceback."""
        from dualentry_cli.client import APIError
        from dualentry_cli.main import main_entrypoint

        monkeypatch.setattr("sys.argv", ["dualentry", "journal-entries", "get", "99999"])
        mock_get_client.get.side_effect = APIError(400, "JournalEntry number 99999 not found")
        with pytest.raises(SystemExit) as exc:
            main_entrypoint()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "JournalEntry number 99999 not found" in captured.err
        assert "Traceback" not in captured.err
        assert "click.exceptions" not in captured.err

    def test_main_entrypoint_404_no_traceback(self, mock_get_client, monkeypatch, capsys):
        from dualentry_cli.client import APIError
        from dualentry_cli.main import main_entrypoint

        monkeypatch.setattr("sys.argv", ["dualentry", "journal-entries", "get", "99999"])
        mock_get_client.get.side_effect = APIError(404, "Resource not found.")
        with pytest.raises(SystemExit) as exc:
            main_entrypoint()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Resource not found." in captured.err
        assert "Traceback" not in captured.err

    def test_main_entrypoint_500_no_traceback(self, mock_get_client, monkeypatch, capsys):
        from dualentry_cli.client import APIError
        from dualentry_cli.main import main_entrypoint

        monkeypatch.setattr("sys.argv", ["dualentry", "invoices", "list"])
        mock_get_client.get.side_effect = APIError(500, "Server error (500).")
        with pytest.raises(SystemExit) as exc:
            main_entrypoint()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err

    def test_prefix_stripped_on_get(self, mock_get_client):
        mock_get_client.get.return_value = {"internal_id": 421163, "number": 3}
        result = runner.invoke(app, ["journal-entries", "get", "JE-3"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/journal-entries/3/")

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


class TestParityResourceCommands:
    def test_product_tax_codes_crud_paths(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["product-tax-codes", "list"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_with("/product-tax-codes/", params={"limit": 20, "offset": 0})

    def test_custom_fields_delete(self, mock_get_client):
        result = runner.invoke(app, ["custom-fields", "delete", "9"])
        assert result.exit_code == 0
        mock_get_client.delete.assert_called_once_with("/custom-fields/9/")

    def test_vat_rates_read_only(self):
        from dualentry_cli.main import app as cli_app

        group = next(g for g in cli_app.registered_groups if g.name == "vat-rates")
        commands = {c.name for c in group.typer_instance.registered_commands}
        assert commands == {"list", "get"}

    def test_statistical_journal_date_filters_use_api_names(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(
            app,
            [
                "statistical-journals",
                "list",
                "--date-start",
                "2025-01-01",
                "--date-end",
                "2025-03-31",
                "--period-start",
                "2025-01-01",
                "--period-end",
                "2025-03-31",
            ],
        )
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with(
            "/statistical-journals/",
            params={
                "date_start": "2025-01-01",
                "date_end": "2025-03-31",
                "period_start": "2025-01-01",
                "period_end": "2025-03-31",
                "limit": 20,
                "offset": 0,
            },
        )

    def test_statistical_journal_add_attachments(self, mock_get_client, tmp_path):
        mock_get_client.post.return_value = {"number": 1}
        upload = tmp_path / "note.txt"
        upload.write_text("hello")
        result = runner.invoke(app, ["statistical-journals", "add-attachments", "3", "--file", str(upload)])
        assert result.exit_code == 0
        mock_get_client.post.assert_called_once()
        args, kwargs = mock_get_client.post.call_args
        assert args[0] == "/statistical-journals/3/attachments/"
        assert kwargs["files"][0][0] == "files"
        assert kwargs["files"][0][1][0] == "note.txt"

    def test_statistical_journal_csv_ids_are_sent_as_a_flat_list(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["statistical-journals", "list", "--number", "1,2", "--number", "3", "--account-id", "5"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with(
            "/statistical-journals/",
            params={"number": [1, 2, 3], "account_id": [5], "limit": 20, "offset": 0},
        )

    def test_statistical_journal_list_rejects_non_integer_csv(self):
        result = runner.invoke(app, ["statistical-journals", "list", "--number", "1,abc"])
        assert result.exit_code == 2
        assert "comma-separated integers" in result.output
        assert "abc" in result.output


class TestClassificationsLinesCommands:
    def test_list_with_no_filters(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["classifications-lines", "list"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/classifications-lines/", params={"limit": 20, "offset": 0})

    def test_every_filter_maps_to_its_api_name(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(
            app,
            ["classifications-lines", "list", "--search", "east", "--classification", "3,4", "--id", "7", "--name", "Eas", "--active"],
        )
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with(
            "/classifications-lines/",
            params={
                "search": "east",
                "classification_id": [3, 4],
                "id": [7],
                "name": "Eas",
                "is_active": True,
                "limit": 20,
                "offset": 0,
            },
        )

    def test_inactive_sends_false_rather_than_dropping_the_filter(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["classifications-lines", "list", "--inactive"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/classifications-lines/", params={"is_active": False, "limit": 20, "offset": 0})

    @pytest.mark.parametrize("flag", ["--classification", "--id"])
    @pytest.mark.parametrize("value", ["3,abc", "", ",", " , "])
    def test_id_filters_reject_bad_or_empty_input_before_calling_the_api(self, flag, value, mock_get_client):
        result = runner.invoke(app, ["classifications-lines", "list", flag, value])
        assert result.exit_code == 2
        assert "comma-separated integers" in result.output
        mock_get_client.get.assert_not_called()

    def test_repeated_id_flags_merge(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["classifications-lines", "list", "--id", "1,2", "--id", "3"])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/classifications-lines/", params={"id": [1, 2, 3], "limit": 20, "offset": 0})

    def test_empty_name_is_not_sent(self, mock_get_client):
        mock_get_client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["classifications-lines", "list", "--name", ""])
        assert result.exit_code == 0
        mock_get_client.get.assert_called_once_with("/classifications-lines/", params={"limit": 20, "offset": 0})

    def test_all_truncation_hint_repeats_every_filter(self, mock_get_client):
        mock_get_client.paginate.return_value = {
            "items": [{"id": 1, "name": "East", "is_active": False, "classification_id": 3, "classification_name": "Region"}],
            "count": 250000,
            "next_offset": 100000,
        }
        result = runner.invoke(
            app,
            ["classifications-lines", "list", "--all", "--search", "north east", "--classification", "3,4", "--id", "7", "--name", "Eas", "--inactive"],
        )
        assert result.exit_code == 0
        hint = result.output.splitlines()[-1].strip()
        assert hint == ("dualentry classifications-lines list --all --offset 100000 --search 'north east' --classification 3,4 --id 7 --name Eas --inactive")


class TestUnknownCommandSuggestions:
    """HelpfulGroup must catch typer's UsageError, not click's (see typer >= 0.26)."""

    @pytest.mark.usefixtures("mock_get_client")
    def test_typo_suggests_closest_command(self):
        result = runner.invoke(app, ["journal-entrie"])
        assert result.exit_code == 2
        assert "Unknown command 'journal-entrie'" in result.output
        assert "journal-entries" in result.output

    @pytest.mark.usefixtures("mock_get_client")
    def test_short_prefix_suggests_long_command(self):
        """cutoff=0.4 catches prefixes that typer's default 0.6 would miss."""
        result = runner.invoke(app, ["bank"])
        assert result.exit_code == 2
        assert "bank-transfers" in result.output

    @pytest.mark.usefixtures("mock_get_client")
    def test_unmatchable_command_still_shows_help(self):
        result = runner.invoke(app, ["zzzzzz"])
        assert result.exit_code == 2
        assert "Unknown command 'zzzzzz'" in result.output
        assert "Did you mean" not in result.output


class TestListAllTruncation:
    def test_all_passes_offset_to_paginate(self, mock_get_client):
        mock_get_client.paginate.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["invoices", "list", "--all", "--offset", "100"])
        assert result.exit_code == 0
        mock_get_client.paginate.assert_called_once_with("/invoices/", params={}, start_offset=100)

    def test_all_truncation_prints_resume_command(self, mock_get_client):
        mock_get_client.paginate.return_value = {
            "items": [{"internal_id": 1, "number": 1}],
            "count": 250000,
            "next_offset": 100000,
        }
        result = runner.invoke(app, ["invoices", "list", "--all", "--search", "acme", "--company", "9"])
        assert result.exit_code == 0
        assert "reached 100000 of 250000" in result.output
        assert "dualentry invoices list --all --offset 100000" in result.output
        assert "--search acme" in result.output
        assert "--company 9" in result.output
        # Warning must come after the list so users see it without scrolling up.
        assert result.output.index("Showing") < result.output.index("reached 100000 of 250000")
        mock_get_client.paginate.assert_called_once_with(
            "/invoices/",
            params={"search": "acme", "company_id": "9"},
            start_offset=0,
        )

    def test_resume_command_helper_for_nested_path(self):
        from dualentry_cli.commands import _resume_all_command

        cmd = _resume_all_command("recurring/invoices", 200, {"status": "posted"})
        assert cmd == "dualentry recurring invoices list --all --offset 200 --status posted"

    @pytest.mark.parametrize(("value", "expected"), [(True, "--active"), (False, "--inactive")])
    def test_resume_command_spells_boolean_filters_as_on_off_flags(self, value, expected):
        from dualentry_cli.commands import _resume_all_command

        cmd = _resume_all_command("classifications-lines", 10, {"is_active": value}, {"is_active": ("--active", "--inactive")})
        assert cmd == f"dualentry classifications-lines list --all --offset 10 {expected}"

    def test_resume_command_quotes_values_with_spaces(self):
        from dualentry_cli.commands import _resume_all_command

        cmd = _resume_all_command("invoices", 10, {"search": "acme corp"})
        assert cmd == "dualentry invoices list --all --offset 10 --search 'acme corp'"

    def test_statistical_journals_hint_keeps_their_own_filters(self, mock_get_client):
        mock_get_client.paginate.return_value = {"items": [], "count": 250000, "next_offset": 100000}
        result = runner.invoke(app, ["statistical-journals", "list", "--all", "--number", "1,2", "--date-start", "2025-01-01"])
        assert result.exit_code == 0
        assert "--date-start 2025-01-01 --number 1,2" in result.output

    def test_complete_all_does_not_warn(self, mock_get_client):
        mock_get_client.paginate.return_value = {
            "items": [{"internal_id": 1, "number": 1}],
            "count": 1,
        }
        result = runner.invoke(app, ["invoices", "list", "--all"])
        assert result.exit_code == 0
        assert "Warning" not in result.output
        assert "stopped at the" not in result.output
