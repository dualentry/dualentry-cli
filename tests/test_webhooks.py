"""Tests for webhooks commands."""

from __future__ import annotations

import json
import re
import time
from unittest.mock import MagicMock, patch

import pytest
import typer.main
from typer.testing import CliRunner

from dualentry_cli.main import app

runner = CliRunner()

UUID = "3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b"

_WEBHOOK = {
    "uuid": UUID,
    "url": "https://hooks.example.com/dualentry",
    "topics": ["invoice.created", "bill.posted"],
    "is_active": True,
    "disabled_at": None,
    "disabled_reason": "",
    "created_at": "2026-10-01T09:00:00+00:00",
    "last_modified_at": "2026-10-02T09:00:00+00:00",
}

_DISABLED = {**_WEBHOOK, "is_active": False, "disabled_at": "2026-10-05T00:00:00+00:00", "disabled_reason": "too many failures"}

_DELIVERY = {
    "event_id": "9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
    "topic": "invoice.created",
    "status": "failed",
    "attempts": 3,
    "response_status": 500,
    "last_error": "upstream timeout",
    "created_at": "2026-10-03T10:11:12+00:00",
    "delivered_at": None,
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


def test_registers_every_webhook_operation():
    commands = set(typer.main.get_command(app).commands["webhooks"].commands)
    assert commands == {"topics", "list", "get", "create", "update", "delete", "deliveries"}


class TestTopics:
    def test_human_output_is_one_name_per_line(self, client):
        client.get.return_value = [{"name": "bill.posted"}, {"name": "invoice.created"}]
        result = runner.invoke(app, ["webhooks", "topics"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with("/webhooks/topics/")
        assert result.output.splitlines()[-2:] == ["bill.posted", "invoice.created"]

    def test_json_output_is_the_api_list(self, client):
        client.get.return_value = [{"name": "bill.posted"}]
        result = runner.invoke(app, ["webhooks", "topics", "-o", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == [{"name": "bill.posted"}]


class TestList:
    def test_no_filters(self, client):
        client.get.return_value = {"items": [_WEBHOOK], "count": 1}
        result = runner.invoke(app, ["webhooks", "list"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with("/webhooks/", params={"limit": 20, "offset": 0})
        out = _flat(result.output)
        assert UUID in out
        assert "https://hooks" in out
        assert "active" in out

    @pytest.mark.parametrize(("flag", "expected"), [("--active", True), ("--inactive", False)])
    def test_active_filter_is_sent_including_false(self, flag, expected, client):
        client.get.return_value = {"items": [], "count": 0}
        result = runner.invoke(app, ["webhooks", "list", flag, "--search", "hooks"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with("/webhooks/", params={"search": "hooks", "is_active": expected, "limit": 20, "offset": 0})

    @pytest.mark.parametrize(("flag", "expected"), [("--active", "--active"), ("--inactive", "--inactive")])
    def test_truncated_all_hint_repeats_every_filter(self, flag, expected, client):
        client.paginate.return_value = {"items": [_WEBHOOK], "count": 250000, "next_offset": 100000}
        result = runner.invoke(app, ["webhooks", "list", "--all", flag, "--search", "acme corp"])
        assert result.exit_code == 0, result.output
        hint = result.output.splitlines()[-1].strip()
        assert hint == f"dualentry webhooks list --all --offset 100000 --search 'acme corp' {expected}"

    def test_auto_disabled_webhook_is_marked_disabled(self, client):
        client.get.return_value = {"items": [_DISABLED], "count": 1}
        result = runner.invoke(app, ["webhooks", "list"])
        assert "disabled" in _flat(result.output)


class TestGet:
    def test_gets_by_uuid(self, client):
        client.get.return_value = _WEBHOOK
        result = runner.invoke(app, ["webhooks", "get", UUID])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with(f"/webhooks/{UUID}/", params=None)
        assert "invoice.created" in result.output

    def test_auto_disabled_webhook_says_when_and_why(self, client):
        client.get.return_value = _DISABLED
        result = runner.invoke(app, ["webhooks", "get", UUID])
        assert "disabled 2026-10-05: too many failures" in _flat(result.output)

    @pytest.mark.parametrize("command", [["get"], ["delete"], ["deliveries"], ["update", "--inactive"]])
    def test_malformed_uuid_is_rejected_before_any_request(self, command, client):
        result = runner.invoke(app, ["webhooks", command[0], "not-a-uuid", *command[1:]])
        assert result.exit_code == 2
        assert "not-a-uuid" in _flat(result.output)
        client.get.assert_not_called()
        client.patch.assert_not_called()
        client.delete.assert_not_called()


class TestCreate:
    def test_sends_url_and_topics_and_shows_secret_once_warning(self, client):
        client.post.return_value = {**_WEBHOOK, "secret": "whsec_example_only"}
        result = runner.invoke(app, ["webhooks", "create", "--url", _WEBHOOK["url"], "-t", "invoice.created", "-t", "bill.posted"])
        assert result.exit_code == 0, result.output
        client.post.assert_called_once_with("/webhooks/", json={"url": _WEBHOOK["url"], "topics": ["invoice.created", "bill.posted"]})
        out = _flat(result.output)
        assert "whsec_example_only" in out
        assert "will not show it again" in out
        assert "receive no events" not in out

    def test_json_output_keeps_the_secret(self, client):
        client.post.return_value = {**_WEBHOOK, "secret": "whsec_example_only"}
        result = runner.invoke(app, ["webhooks", "create", "--url", _WEBHOOK["url"], "-t", "invoice.created", "-o", "json"])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["secret"] == "whsec_example_only"

    def test_no_topics_is_allowed_but_warned(self, client):
        client.post.return_value = {**_WEBHOOK, "topics": [], "secret": "whsec_example_only"}
        result = runner.invoke(app, ["webhooks", "create", "--url", _WEBHOOK["url"]])
        assert result.exit_code == 0, result.output
        client.post.assert_called_once_with("/webhooks/", json={"url": _WEBHOOK["url"], "topics": []})
        assert "will receive no events" in _flat(result.output)

    def test_url_is_required(self, client):
        result = runner.invoke(app, ["webhooks", "create", "-t", "invoice.created"])
        assert result.exit_code == 2
        client.post.assert_not_called()


class TestUpdate:
    @pytest.mark.parametrize(
        ("args", "body"),
        [
            (["--url", "https://new.example.com"], {"url": "https://new.example.com"}),
            (["-t", "bill.posted", "-t", "invoice.created"], {"topics": ["bill.posted", "invoice.created"]}),
            (["--clear-topics"], {"topics": []}),
            (["--active"], {"is_active": True}),
            (["--inactive"], {"is_active": False}),
        ],
    )
    def test_patches_only_what_was_passed(self, args, body, client):
        client.patch.return_value = _WEBHOOK
        result = runner.invoke(app, ["webhooks", "update", UUID, *args])
        assert result.exit_code == 0, result.output
        client.patch.assert_called_once_with(f"/webhooks/{UUID}/", json=body)

    def test_clearing_topics_warns(self, client):
        client.patch.return_value = {**_WEBHOOK, "topics": []}
        result = runner.invoke(app, ["webhooks", "update", UUID, "--clear-topics"])
        assert "will receive no events" in _flat(result.output)

    def test_topic_and_clear_topics_together_are_rejected(self, client):
        result = runner.invoke(app, ["webhooks", "update", UUID, "-t", "bill.posted", "--clear-topics"])
        assert result.exit_code == 2
        assert "not both" in _flat(result.output)
        client.patch.assert_not_called()

    def test_nothing_to_change_is_rejected(self, client):
        result = runner.invoke(app, ["webhooks", "update", UUID])
        assert result.exit_code == 2
        out = _flat(result.output)
        assert "nothing to change" in out
        assert "Invalid value" not in out
        client.patch.assert_not_called()


class TestDelete:
    def test_deletes_by_uuid_and_says_history_went_too(self, client):
        client.delete.return_value = {"success": True, "errors": {}}
        result = runner.invoke(app, ["webhooks", "delete", UUID])
        assert result.exit_code == 0, result.output
        client.delete.assert_called_once_with(f"/webhooks/{UUID}/")
        assert "with its delivery history" in result.output


class TestDeliveries:
    def test_one_page(self, client):
        client.get.return_value = {"items": [_DELIVERY], "count": 1}
        result = runner.invoke(app, ["webhooks", "deliveries", UUID, "--limit", "5"])
        assert result.exit_code == 0, result.output
        client.get.assert_called_once_with(f"/webhooks/{UUID}/deliveries/", params={"limit": 5, "offset": 0})
        out = _flat(result.output)
        assert "failed" in out
        assert "upstream timeout" in out

    def test_all_pages_from_offset(self, client):
        client.paginate.return_value = {"items": [_DELIVERY], "count": 1}
        result = runner.invoke(app, ["webhooks", "deliveries", UUID, "--all", "--offset", "40"])
        assert result.exit_code == 0, result.output
        client.paginate.assert_called_once_with(f"/webhooks/{UUID}/deliveries/", start_offset=40)
        assert "Warning" not in result.output

    def test_truncated_all_prints_a_resume_command_for_this_command(self, client):
        client.paginate.return_value = {"items": [_DELIVERY], "count": 250000, "next_offset": 100000}
        result = runner.invoke(app, ["webhooks", "deliveries", UUID, "--all"])
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[-1].strip() == f"dualentry webhooks deliveries {UUID} --all --offset 100000"


@pytest.fixture
def new_york_time(monkeypatch):
    """Pin the process timezone, so local-time rendering is deterministic."""
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset is not available on this platform")
    monkeypatch.setenv("TZ", "America/New_York")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@pytest.mark.usefixtures("new_york_time")
class TestDeliveryTimes:
    def test_utc_timestamps_are_shown_in_local_time(self, client):
        client.get.return_value = {"items": [_DELIVERY], "count": 1}
        result = runner.invoke(app, ["webhooks", "deliveries", UUID])
        out = _flat(result.output)
        assert "2026-10-03 06:11" in out
        assert "10:11" not in out

    def test_naive_timestamp_is_shown_as_given(self):
        from dualentry_cli.output import _local_minute

        assert _local_minute("2026-10-03T10:11:12") == "2026-10-03 10:11"
