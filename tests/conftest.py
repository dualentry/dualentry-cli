"""Shared pytest fixtures for dualentry-cli tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def disable_cli_update_checks(request, monkeypatch):
    """
    Keep update notices out of CliRunner output.

    ``check_for_updates`` prints to stderr; Click's CliRunner folds that into
    ``result.output``, which breaks tests that ``json.loads`` the whole stream.
    Once a newer tag exists than ``__version__``, a background cache refresh
    makes that flaky across the suite. Skip for ``test_updater``, which covers
    the notice itself.
    """
    if request.module.__name__.endswith("test_updater"):
        yield
        return
    monkeypatch.setattr("dualentry_cli.updater.check_for_updates", lambda: None)
    yield
