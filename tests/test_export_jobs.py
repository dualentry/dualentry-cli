"""Tests for export-jobs commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dualentry_cli.main import app

runner = CliRunner()

_JOB = {
    "id": 42,
    "integration_id": 7,
    "status": "pending",
    "error": None,
    "created_at": "2026-09-29T12:00:00Z",
    "started_at": None,
    "completed_at": None,
}


def test_create_without_integration_id():
    client = MagicMock()
    client.post.return_value = {"job": _JOB, "deduplicated": False}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "create"])
    assert result.exit_code == 0
    client.post.assert_called_once_with("/export-jobs/", json=None)
    assert "42" in result.output


def test_create_with_integration_id_json():
    client = MagicMock()
    client.post.return_value = {"job": _JOB, "deduplicated": False}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "create", "--integration-id", "7", "--format", "json"])
    assert result.exit_code == 0
    client.post.assert_called_once_with("/export-jobs/", json={"integration_id": 7})
    parsed = json.loads(result.output)
    assert parsed["job"]["id"] == 42
    assert parsed["deduplicated"] is False


def test_create_deduplicated_prints_note():
    client = MagicMock()
    client.post.return_value = {"job": {**_JOB, "status": "running"}, "deduplicated": True}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "create", "--integration-id", "7"])
    assert result.exit_code == 0
    assert "deduplicated" in result.output.lower() or "already running" in result.output.lower()


def test_list():
    client = MagicMock()
    client.get.return_value = {"items": [_JOB], "count": 1}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "list"])
    assert result.exit_code == 0
    client.get.assert_called_once_with("/export-jobs/", params={"limit": 20, "offset": 0})
    assert "42" in result.output


def test_list_status_filter_repeatable():
    client = MagicMock()
    client.get.return_value = {"items": [], "count": 0}
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(
            app,
            ["export-jobs", "list", "--status", "pending", "--status", "running"],
        )
    assert result.exit_code == 0
    client.get.assert_called_once_with(
        "/export-jobs/",
        params={"limit": 20, "offset": 0, "status": ["pending", "running"]},
    )


def test_list_rejects_invalid_status():
    with patch("dualentry_cli.main.get_client", return_value=MagicMock()):
        result = runner.invoke(app, ["export-jobs", "list", "--status", "archived"])
    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert "archived" in result.output


def test_get():
    client = MagicMock()
    client.get.return_value = _JOB
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "get", "42"])
    assert result.exit_code == 0
    client.get.assert_called_once_with("/export-jobs/42/", params=None)
    assert "42" in result.output


def test_wait_completes():
    client = MagicMock()
    client.get.side_effect = [
        {**_JOB, "status": "running"},
        {**_JOB, "status": "completed", "completed_at": "2026-09-29T12:05:00Z"},
    ]
    with (
        patch("dualentry_cli.main.get_client", return_value=client),
        patch("dualentry_cli.commands.export_jobs.time.sleep") as sleep,
    ):
        result = runner.invoke(app, ["export-jobs", "wait", "42", "--interval", "0.5"])
    assert result.exit_code == 0
    assert client.get.call_count == 2
    sleep.assert_called_once()
    assert "completed" in result.output.lower()
    assert "job 42 is running" in result.output


def test_wait_failed_exits_one():
    client = MagicMock()
    client.get.return_value = {
        **_JOB,
        "status": "failed",
        "error": "Export failed. Contact support with job id.",
        "completed_at": "2026-09-29T12:05:00Z",
    }
    with patch("dualentry_cli.main.get_client", return_value=client):
        result = runner.invoke(app, ["export-jobs", "wait", "42"])
    assert result.exit_code == 1


def test_wait_timeout_exits_one():
    client = MagicMock()
    client.get.return_value = {**_JOB, "status": "running"}
    with (
        patch("dualentry_cli.main.get_client", return_value=client),
        patch("dualentry_cli.commands.export_jobs.time.sleep"),
        patch("dualentry_cli.commands.export_jobs.time.monotonic", side_effect=[0.0, 0.0, 10.0]),
    ):
        result = runner.invoke(app, ["export-jobs", "wait", "42", "--timeout", "5", "--interval", "1"])
    assert result.exit_code == 1
    assert "Timed out" in result.output


def test_export_jobs_commands_registered():
    group = next(g for g in app.registered_groups if g.name == "export-jobs")
    names = {c.name for c in group.typer_instance.registered_commands}
    assert names == {"create", "list", "get", "wait"}
