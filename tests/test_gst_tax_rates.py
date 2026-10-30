"""Tests for gst-tax-rates commands."""

from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

import pytest
import typer.main
from typer.testing import CliRunner

from dualentry_cli.main import app
from dualentry_cli.output import _fraction_as_percent

runner = CliRunner()

_RATE = {
    "id": 12,
    "country_code": "IN",
    "name": "GST standard intra-state",
    "rate": "0.180000",
    "tax_treatment": "STANDARD",
    "supply_category": "INTRA_STATE",
    "region": "KA",
    "valid_from": "2017-07-01",
    "valid_to": None,
    "is_active": True,
    "is_system": True,
    "description": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "components": [
        {"id": 2, "component_type": "SGST", "rate": "0.090000", "region": "KA", "position": 1},
        {"id": 1, "component_type": "CGST", "rate": "0.090000", "region": None, "position": 0},
    ],
}


def _flat(output: str) -> str:
    """Strip ANSI codes and rich box borders, and collapse wrapping, so messages match in CI too."""
    plain = re.sub(r"\x1b\[[0-9;]*m", "", output)
    return " ".join(plain.replace("│", " ").split())


@pytest.fixture
def client():
    mock = MagicMock()
    with patch("dualentry_cli.main.get_client", return_value=mock):
        yield mock


def test_is_read_only():
    assert set(typer.main.get_command(app).commands["gst-tax-rates"].commands) == {"list", "get"}


class TestList:
    def test_no_filters(self, client):
        client.get.return_value = {"items": [_RATE], "count": 1}
        result = runner.invoke(app, ["gst-tax-rates", "list"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with("/gst-tax-rates/", params={"limit": 20, "offset": 0})
        out = _flat(result.output)
        assert "GST standard intra-state" in out
        assert "IN (KA)" in out
        assert "18%" in out
        assert "0.180000" not in out

    def test_every_filter_maps_to_its_api_name(self, client):
        client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(
            app,
            [
                "gst-tax-rates", "list",
                "--country", "IN", "--country", "au",
                "--treatment", "zero_rated",
                "--inactive",
                "--updated-after", "2026-01-01T00:00:00Z",
                "--updated-before", "2026-06-30T23:59:59+10:00",
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with(
            "/gst-tax-rates/",
            params={
                "country_code": ["IN", "AU"],
                "tax_treatment": "ZERO_RATED",
                "is_active": False,
                "updated_after": "2026-01-01T00:00:00Z",
                "updated_before": "2026-06-30T23:59:59+10:00",
                "limit": 20,
                "offset": 0,
            },
        )

    @pytest.mark.parametrize(("flag", "value"), [("--country", "US"), ("--country", "GB"), ("--treatment", "ZERO")])
    def test_unknown_choice_is_rejected_before_any_request(self, flag, value, client):
        result = runner.invoke(app, ["gst-tax-rates", "list", flag, value])
        assert result.exit_code == 2
        assert "is not one of" in _flat(result.output)
        client.get.assert_not_called()

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            ("2026-01-01T00:00:00", "has no timezone"),
            ("2026-01-01", "has no timezone"),
            ("yesterday", "expected an ISO 8601 timestamp"),
        ],
    )
    @pytest.mark.parametrize("flag", ["--updated-after", "--updated-before"])
    def test_updated_filters_need_a_timezone_aware_iso_timestamp(self, flag, value, message, client):
        result = runner.invoke(app, ["gst-tax-rates", "list", flag, value])
        assert result.exit_code == 2
        assert message in _flat(result.output)
        client.get.assert_not_called()

    def test_json_output_keeps_the_api_fraction(self, client):
        client.get.return_value = {"items": [_RATE], "count": 1}
        result = runner.invoke(app, ["gst-tax-rates", "list", "-o", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["items"][0]["rate"] == "0.180000"


class TestGet:
    def test_gets_by_id_with_components_in_position_order(self, client):
        client.get.return_value = _RATE
        result = runner.invoke(app, ["gst-tax-rates", "get", "12"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with("/gst-tax-rates/12/", params=None)
        out = _flat(result.output)
        assert "IN (KA)" in out
        assert "INTRA_STATE" in out
        assert "open-ended" in out
        assert out.index("CGST") < out.index("SGST")
        assert "9%" in out

    def test_rate_without_components_has_no_breakdown(self, client):
        client.get.return_value = {**_RATE, "components": [], "supply_category": None, "region": None}
        result = runner.invoke(app, ["gst-tax-rates", "get", "12"])
        out = _flat(result.output)
        assert "Components" not in out
        assert "Supply" not in out

    @pytest.mark.parametrize("value", ["abc", "1.5", "GST-12"])
    def test_id_must_be_an_integer(self, value, client):
        result = runner.invoke(app, ["gst-tax-rates", "get", value])
        assert result.exit_code == 2
        client.get.assert_not_called()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.100000", "10%"),
        ("0.087500", "8.75%"),
        ("0.000000", "0%"),
        ("0.150000", "15%"),
        (0.05, "5%"),
        ("n/a", "n/a"),
        ("NaN", "NaN"),
        ("Infinity", "Infinity"),
    ],
)
def test_fraction_as_percent(value, expected):
    assert _fraction_as_percent(value) == expected
