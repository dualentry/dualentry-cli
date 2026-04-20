from dualentry_cli.output import format_output


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
