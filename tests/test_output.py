import json


class TestFormatOutput:
    def test_json_format(self, capsys):
        from dualentry_cli.output import format_output

        data = {"items": [{"id": 1, "name": "Test"}], "count": 1}
        format_output(data, fmt="json")
        captured = capsys.readouterr()
        assert json.loads(captured.out) == data

    def test_table_format_list(self, capsys):
        from dualentry_cli.output import format_output

        data = {"items": [{"id": 1, "number": "INV-001", "total": "100.00"}, {"id": 2, "number": "INV-002", "total": "200.00"}], "count": 2}
        format_output(data, fmt="table")
        captured = capsys.readouterr()
        assert "INV-001" in captured.out
        assert "INV-002" in captured.out

    def test_table_format_single_item(self, capsys):
        from dualentry_cli.output import format_output

        data = {"id": 1, "number": "INV-001", "total": "100.00"}
        format_output(data, fmt="table")
        captured = capsys.readouterr()
        assert "INV-001" in captured.out


class TestTruncatedLinesWarning:
    def _je(self, *, has_more_lines: bool, lines_count: int | None, n_items: int = 2) -> dict:
        items = [
            {
                "account_name": f"Account {i}",
                "memo": f"Line {i}",
                "debit": "10.00" if i % 2 else "0.00",
                "credit": "0.00" if i % 2 else "10.00",
            }
            for i in range(1, n_items + 1)
        ]
        record = {
            "internal_id": 3,
            "date": "2026-01-15",
            "company_name": "Acme",
            "currency_iso_4217_code": "USD",
            "record_status": "posted",
            "memo": "Payroll",
            "items": items,
            "has_more_lines": has_more_lines,
        }
        if lines_count is not None:
            record["lines_count"] = lines_count
        return record

    def test_warns_when_has_more_lines(self, capsys):
        from dualentry_cli.output import format_output

        format_output(self._je(has_more_lines=True, lines_count=250, n_items=100), resource="journal-entry")
        captured = capsys.readouterr()
        assert "JOURNAL ENTRY" in captured.out
        assert "Account 1" in captured.out
        assert "Warning: showing 100 of 250 lines. The API caps inline lines at 100." in captured.out
        assert captured.out.index("Account 1") < captured.out.index("Warning:")

    def test_no_warn_when_complete(self, capsys):
        from dualentry_cli.output import format_output

        format_output(self._je(has_more_lines=False, lines_count=2), resource="journal-entry")
        captured = capsys.readouterr()
        assert "JOURNAL ENTRY" in captured.out
        assert "Warning:" not in captured.out

    def test_no_warn_when_flag_absent(self, capsys):
        from dualentry_cli.output import format_output

        record = self._je(has_more_lines=False, lines_count=2)
        del record["has_more_lines"]
        del record["lines_count"]
        format_output(record, resource="journal-entry")
        captured = capsys.readouterr()
        assert "Warning:" not in captured.out

    def test_fallback_without_lines_count(self, capsys):
        from dualentry_cli.output import format_output

        format_output(self._je(has_more_lines=True, lines_count=None), resource="journal-entry")
        captured = capsys.readouterr()
        assert "Warning: showing 2 lines. The API omitted the rest." in captured.out

    def test_invoice_detail_also_warns(self, capsys):
        from dualentry_cli.output import format_output

        data = {
            "internal_id": 1,
            "number": "INV-001",
            "date": "2026-01-15",
            "company_name": "Acme",
            "customer_name": "Buyer",
            "currency_iso_4217_code": "USD",
            "amount": "100.00",
            "items": [{"memo": "Widget", "quantity": "1", "rate": "100.00"}],
            "has_more_lines": True,
            "lines_count": 150,
        }
        format_output(data, resource="invoice")
        captured = capsys.readouterr()
        assert "Warning: showing 1 of 150 lines. The API caps inline lines at 100." in captured.out

    def test_json_keeps_flags_and_skips_warning(self, capsys):
        from dualentry_cli.output import format_output

        data = self._je(has_more_lines=True, lines_count=250, n_items=2)
        format_output(data, resource="journal-entry", fmt="json")
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["has_more_lines"] is True
        assert payload["lines_count"] == 250
        assert "Warning:" not in captured.out
        assert captured.err == ""
