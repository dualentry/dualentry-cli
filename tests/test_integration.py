"""
Integration tests against a live DualEntry API.

Requires:
  - X_API_KEY env var set

Run:
  X_API_KEY=... pytest tests/test_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from dualentry_cli.client import DualEntryClient
from dualentry_cli.config import Config

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def client():
    api_key = os.environ.get("X_API_KEY")
    if not api_key:
        pytest.skip("X_API_KEY not set")
    config = Config()
    c = DualEntryClient(api_url=config.api_url, api_key=api_key)
    yield c
    c.close()


# ── Helpers ─────────────────────────────────────────────────────────


def assert_list(data: dict, min_count: int = 0):
    """Assert data looks like a paginated list response."""
    assert "items" in data, f"Missing 'items' key, got: {list(data.keys())}"
    assert "count" in data, f"Missing 'count' key, got: {list(data.keys())}"
    assert isinstance(data["items"], list)
    assert data["count"] >= min_count


def assert_record(data: dict, required_keys: list[str]):
    """Assert data is a single record with expected keys."""
    for key in required_keys:
        assert key in data, f"Missing key '{key}' in record. Keys: {list(data.keys())}"


# ── Numbered resources (get by number) ──────────────────────────────

NUMBERED_RESOURCES = [
    ("invoices", ["number", "date", "currency_iso_4217_code"]),
    ("bills", ["number", "date", "currency_iso_4217_code"]),
    ("sales-orders", ["number", "date", "currency_iso_4217_code"]),
    ("purchase-orders", ["number", "date", "currency_iso_4217_code"]),
    ("customer-payments", ["number", "date", "currency_iso_4217_code"]),
    ("customer-credits", ["number", "date", "currency_iso_4217_code"]),
    ("customer-prepayments", ["number", "date", "currency_iso_4217_code"]),
    ("customer-prepayment-applications", ["number", "date", "currency_iso_4217_code"]),
    ("customer-deposits", ["number", "date", "currency_iso_4217_code"]),
    ("customer-refunds", ["number", "date", "currency_iso_4217_code"]),
    ("cash-sales", ["number", "date", "currency_iso_4217_code"]),
    ("vendor-payments", ["number", "date", "currency_iso_4217_code"]),
    ("vendor-credits", ["number", "date", "currency_iso_4217_code"]),
    ("vendor-prepayments", ["number", "date", "currency_iso_4217_code"]),
    ("vendor-prepayment-applications", ["number", "date", "currency_iso_4217_code"]),
    ("vendor-refunds", ["number", "date", "currency_iso_4217_code"]),
    ("direct-expenses", ["number", "date", "currency_iso_4217_code"]),
    ("journal-entries", ["number", "date", "currency_iso_4217_code"]),
    ("bank-transfers", ["number", "date"]),
    ("fixed-assets", ["number", "name"]),
]


@pytest.mark.parametrize("path,detail_keys", NUMBERED_RESOURCES, ids=[r[0] for r in NUMBERED_RESOURCES])
def test_numbered_resource_list(client: DualEntryClient, path: str, detail_keys: list[str]):
    data = client.get(f"/{path}/", params={"limit": 2})
    assert_list(data)


@pytest.mark.parametrize("path,detail_keys", NUMBERED_RESOURCES, ids=[r[0] for r in NUMBERED_RESOURCES])
def test_numbered_resource_get(client: DualEntryClient, path: str, detail_keys: list[str]):
    # List first to get a valid number
    data = client.get(f"/{path}/", params={"limit": 1})
    assert_list(data, min_count=1)
    number = data["items"][0]["number"]

    detail = client.get(f"/{path}/{number}/")
    assert_record(detail, detail_keys)


@pytest.mark.parametrize("path,detail_keys", NUMBERED_RESOURCES, ids=[r[0] for r in NUMBERED_RESOURCES])
def test_numbered_resource_search(client: DualEntryClient, path: str, detail_keys: list[str]):
    data = client.get(f"/{path}/", params={"limit": 2, "search": "test"})
    assert_list(data)


@pytest.mark.parametrize("path,detail_keys", NUMBERED_RESOURCES, ids=[r[0] for r in NUMBERED_RESOURCES])
def test_numbered_resource_limit(client: DualEntryClient, path: str, detail_keys: list[str]):
    data = client.get(f"/{path}/", params={"limit": 1})
    assert_list(data)
    assert len(data["items"]) <= 1


@pytest.mark.parametrize("path,detail_keys", NUMBERED_RESOURCES, ids=[r[0] for r in NUMBERED_RESOURCES])
def test_numbered_resource_offset(client: DualEntryClient, path: str, detail_keys: list[str]):
    all_data = client.get(f"/{path}/", params={"limit": 3})
    if all_data["count"] < 2:
        pytest.skip("Not enough records to test offset")
    offset_data = client.get(f"/{path}/", params={"limit": 2, "offset": 1})
    assert_list(offset_data)
    # First item at offset=1 should match second item at offset=0
    assert offset_data["items"][0]["number"] == all_data["items"][1]["number"]


# ── ID-based resources ──────────────────────────────────────────────

ID_RESOURCES = [
    ("customers", "id", ["id", "name"]),
    ("vendors", "id", ["id", "name"]),
    ("items", "id", ["id", "name"]),
    ("companies", "id", ["id", "name"]),
    ("classifications", "id", ["id", "name"]),
    ("contracts", "id", ["id", "name"]),
    ("budgets", "id", ["id", "name"]),
    ("workflows", "id", ["id", "name"]),
]


@pytest.mark.parametrize("path,id_field,detail_keys", ID_RESOURCES, ids=[r[0] for r in ID_RESOURCES])
def test_id_resource_list(client: DualEntryClient, path: str, id_field: str, detail_keys: list[str]):
    data = client.get(f"/{path}/", params={"limit": 2})
    assert_list(data)


@pytest.mark.parametrize("path,id_field,detail_keys", ID_RESOURCES, ids=[r[0] for r in ID_RESOURCES])
def test_id_resource_get(client: DualEntryClient, path: str, id_field: str, detail_keys: list[str]):
    data = client.get(f"/{path}/", params={"limit": 1})
    assert_list(data, min_count=1)
    record_id = data["items"][0][id_field]

    detail = client.get(f"/{path}/{record_id}/")
    assert_record(detail, detail_keys)


# ── Accounts (uses account number in URL) ───────────────────────────


def test_accounts_list(client: DualEntryClient):
    data = client.get("/accounts/", params={"limit": 2})
    assert_list(data)
    if data["items"]:
        assert "number" in data["items"][0]


def test_accounts_get(client: DualEntryClient):
    data = client.get("/accounts/", params={"limit": 1})
    assert_list(data, min_count=1)
    account_number = data["items"][0]["number"]
    detail = client.get(f"/accounts/{account_number}/")
    assert_record(detail, ["number", "name", "account_type"])


# ── Depreciation books (uses string book_code in URL) ───────────────


def test_depreciation_books_list(client: DualEntryClient):
    data = client.get("/depreciation-books/", params={"limit": 2})
    assert_list(data)


def test_depreciation_books_get(client: DualEntryClient):
    data = client.get("/depreciation-books/", params={"limit": 1})
    assert_list(data, min_count=1)
    code = data["items"][0].get("code") or data["items"][0].get("name", "").upper()
    detail = client.get(f"/depreciation-books/{code}/")
    assert_record(detail, ["name"])


# ── Recurring resources ─────────────────────────────────────────────

RECURRING_RESOURCES = [
    "recurring/invoices",
    "recurring/bills",
    "recurring/journal-entries",
]


@pytest.mark.parametrize("path", RECURRING_RESOURCES, ids=[r.replace("/", "-") for r in RECURRING_RESOURCES])
def test_recurring_list(client: DualEntryClient, path: str):
    data = client.get(f"/{path}/", params={"limit": 2})
    assert_list(data)


# ── Pagination ──────────────────────────────────────────────────────


def test_paginate(client: DualEntryClient):
    """paginate() should fetch all pages and combine results."""
    data = client.paginate("/invoices/", page_size=5)
    assert "items" in data
    assert "count" in data
    assert data["count"] == len(data["items"])
    # Should have fetched more than one page worth if enough data exists
    if data["count"] > 5:
        assert len(data["items"]) > 5


def test_paginate_with_filters(client: DualEntryClient):
    """paginate() should forward filter params."""
    data = client.paginate("/invoices/", params={"search": "nonexistent_xyz_12345"}, page_size=5)
    assert_list(data)
    # Unlikely to find anything with gibberish search
    assert data["count"] == 0
