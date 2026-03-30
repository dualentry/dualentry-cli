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
