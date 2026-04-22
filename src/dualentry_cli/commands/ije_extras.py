"""Intercompany journal entry template and validation logic."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

IJE_TEMPLATE = {
    "date": "2026-01-01",
    "memo": "Intercompany transfer",
    "currency_iso_4217_code": "USD",
    "exchange_rate": "1.00000000",
    "record_status": "draft",
    "items": [
        {
            "company_id": 1,
            "account_number": 1000,
            "debit": "1000.00",
            "credit": "0.00",
            "memo": "",
            "position": 0,
            "eliminate": True,
        },
        {
            "company_id": 1,
            "account_number": 2000,
            "debit": "0.00",
            "credit": "1000.00",
            "memo": "",
            "position": 1,
            "eliminate": True,
        },
        {
            "company_id": 2,
            "account_number": 1000,
            "debit": "1000.00",
            "credit": "0.00",
            "memo": "",
            "position": 2,
            "eliminate": True,
        },
        {
            "company_id": 2,
            "account_number": 2000,
            "debit": "0.00",
            "credit": "1000.00",
            "memo": "",
            "position": 3,
            "eliminate": True,
        },
    ],
}


# ── Checks ─────────────────────────────────────────────────────────
# Each check: (payload, client=None) -> list[str]
# Return error strings. Empty list = pass.


def check_items_present(payload: dict, client=None) -> list[str]:
    items = payload.get("items")
    if not items or not isinstance(items, list):
        return ["Payload must contain a non-empty 'items' array."]
    return []


def check_amounts_valid(payload: dict, client=None) -> list[str]:
    errors = []
    for i, item in enumerate(payload.get("items", [])):
        try:
            Decimal(str(item.get("debit", "0")))
            Decimal(str(item.get("credit", "0")))
        except (InvalidOperation, TypeError):
            errors.append(f"Item {i}: invalid debit/credit value.")
    return errors


def check_debits_equal_credits(payload: dict, client=None) -> list[str]:
    total_debits = Decimal(0)
    total_credits = Decimal(0)
    for item in payload.get("items", []):
        total_debits += Decimal(str(item.get("debit", "0")))
        total_credits += Decimal(str(item.get("credit", "0")))
    total_debits = total_debits.quantize(Decimal("0.01"))
    total_credits = total_credits.quantize(Decimal("0.01"))
    if total_debits != total_credits:
        return [f"Total debits ({total_debits}) must equal total credits ({total_credits})."]
    return []


def check_multi_company(payload: dict, client=None) -> list[str]:
    company_ids = {item.get("company_id") for item in payload.get("items", []) if item.get("company_id") is not None}
    if len(company_ids) < 2:
        return ["Intercompany journal entries require lines across at least two distinct companies."]
    return []


def check_company_access(payload: dict, client=None) -> list[str]:
    if client is None:
        return []
    company_ids = {item.get("company_id") for item in payload.get("items", []) if item.get("company_id") is not None}
    if not company_ids:
        return []
    data = client.get("/companies/", params={"limit": 100})
    accessible = {c["id"] for c in data.get("items", [])}
    unknown = company_ids - accessible
    if unknown:
        return [f"Company IDs not accessible: {', '.join(str(c) for c in sorted(unknown))}"]
    return []


# ── Offline checks run in order; later checks assume earlier ones passed.
IJE_OFFLINE_CHECKS = [check_items_present, check_amounts_valid, check_debits_equal_credits, check_multi_company]
IJE_ONLINE_CHECKS = [check_company_access]

IJE_CHECKS = IJE_OFFLINE_CHECKS
IJE_ONLINE_EXTRA_CHECKS = IJE_ONLINE_CHECKS
