from __future__ import annotations

import pytest

from dualentry_cli.main import app

STALE_COMMANDS = [
    ("companies", "create"),
    ("companies", "update"),
    ("budgets", "create"),
    ("budgets", "update"),
    ("depreciation-books", "create"),
    ("depreciation-books", "update"),
    ("paper-checks", "create"),
    ("paper-checks", "update"),
    ("inbox", "get"),
]


def _commands(resource: str) -> set[str]:
    group = next(g for g in app.registered_groups if g.name == resource)
    return {c.name for c in group.typer_instance.registered_commands}


@pytest.mark.parametrize(("resource", "command"), STALE_COMMANDS)
def test_stale_command_is_not_registered(resource: str, command: str):
    assert command not in _commands(resource), f"'dualentry {resource} {command}' has no v2 route and must not be registered"


@pytest.mark.parametrize("resource", ["companies", "budgets", "depreciation-books", "paper-checks"])
def test_read_only_resource_keeps_its_read_commands(resource: str):
    assert _commands(resource) == {"list", "get"}


def test_inbox_keeps_only_list():
    assert _commands("inbox") == {"list"}


def test_paper_checks_has_no_number_lookups():
    assert not _commands("paper-checks") & {"get-number", "get-id"}


def test_writable_resource_is_untouched():
    assert {"create", "update"} <= _commands("invoices")
