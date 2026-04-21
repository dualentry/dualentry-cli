"""Output formatting for DualEntry CLI."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

# Resource name → display prefix (e.g. "invoice" → "IN")
_RECORD_PREFIX: dict[str, str] = {
    "invoice": "IN",
    "bill": "BI",
    "sales-order": "SO",
    "purchase-order": "PO",
    "customer-payment": "CP",
    "customer-credit": "CC",
    "customer-prepayment": "CPP",
    "customer-prepayment-application": "CPA",
    "customer-deposit": "CD",
    "customer-refund": "CR",
    "cash-sale": "CS",
    "direct-expense": "DE",
    "vendor-payment": "VP",
    "vendor-credit": "VC",
    "vendor-prepayment": "VPP",
    "vendor-prepayment-application": "VPA",
    "vendor-refund": "VR",
    "journal-entry": "JE",
    "intercompany-journal-entry": "IJE",
    "bank-transfer": "BT",
    "fixed-asset": "FA",
}


def _fmt_id(record_id, resource: str = "") -> str:
    """Format a record ID with its prefix, e.g. 135934 → IN-135934 (matches UI display)."""
    if record_id is None:
        return "-"
    prefix = _RECORD_PREFIX.get(resource, "")
    if prefix:
        return f"{prefix}-{record_id}"
    return str(record_id)


def format_output(data: dict, resource: str = "generic", fmt: str = "human") -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2))
        return

    if "items" in data and "count" in data:
        _print_list(data, resource)
        return

    _print_detail(data, resource)


# ── Dispatcher ───────────────────────────────────────────────────────

# Map resource types to (list_fn, detail_fn)
_FORMATTERS: dict[str, tuple] = {}


def _register(resource: str, list_fn, detail_fn):
    _FORMATTERS[resource] = (list_fn, detail_fn)


def _print_list(data: dict, resource: str) -> None:
    items = data["items"]
    if not items:
        console.print("No results.")
        return

    list_fn = _FORMATTERS.get(resource, (None, None))[0]
    if list_fn:
        list_fn(items)
    else:
        _print_generic_list(items)

    if "count" in data:
        console.print(f"\n[dim]Showing {len(items)} of {data['count']}[/dim]")


def _print_detail(data: dict, resource: str) -> None:
    detail_fn = _FORMATTERS.get(resource, (None, None))[1]
    if detail_fn:
        detail_fn(data)
    else:
        _print_generic_detail(data)


# ── Shared: Transaction list (records with #, Date, Counterparty, Amount) ──


def _transaction_list(
    items: list[dict],
    title: str,
    counterparty_label: str,
    counterparty_field: str,
    show_due_date: bool = False,
    show_paid: bool = False,
    show_remaining: bool = False,
    show_memo: bool = False,
    resource: str = "",
):
    table = Table(title=title, show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("#", style="bold", justify="right")
    table.add_column("Date", justify="center")
    table.add_column("Company")
    table.add_column(counterparty_label, min_width=16)
    if show_due_date:
        table.add_column("Due Date", justify="center")
    if show_memo:
        table.add_column("Memo", max_width=20)
    table.add_column("Currency", justify="center")
    table.add_column("Amount", justify="right", style="bold")
    if show_paid:
        table.add_column("Paid", justify="right")
        table.add_column("Due", justify="right")
    if show_remaining:
        table.add_column("Remaining", justify="right")
    table.add_column("Status")

    for r in items:
        currency = r.get("currency_iso_4217_code", "")
        row = [
            _fmt_id(r.get("internal_id"), resource),
            str(r.get("number", "")),
            r.get("date", "-"),
            r.get("company_name", "-"),
            r.get(counterparty_field) or "-",
        ]
        if show_due_date:
            row.append(r.get("due_date") or "-")
        if show_memo:
            memo = r.get("memo", "") or ""
            row.append(memo[:20] + ("..." if len(memo) > 20 else ""))
        row.append(currency)
        row.append(_money(r.get("amount"), currency))
        if show_paid:
            row.append(_money(r.get("paid_total"), currency))
            row.append(_money(r.get("amount_due"), currency))
        if show_remaining:
            row.append(_money(r.get("remaining_amount"), currency))
        row.append(_status_badge(r.get("record_status", "")))

        table.add_row(*row)

    console.print(table)


# ── Shared: Transaction detail (records with line items, totals) ─────


def _transaction_detail(
    record: dict,
    record_type: str,
    counterparty_label: str,
    counterparty_field: str,
    due_color: str = "green",
    resource: str = "",
):
    currency = record.get("currency_iso_4217_code") or record.get("company_currency", "")

    header = Text()
    header.append(record_type.upper(), style="bold")
    header.append(f"  {_fmt_id(record.get('internal_id'), resource)}", style="bold cyan")
    status = record.get("record_status", "")
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    grid = Table.grid(padding=(0, 4))
    grid.add_column(min_width=30)
    grid.add_column(min_width=30)

    left = Text()
    left.append("Company: ", style="dim")
    left.append(record.get("company_name", "-"), style="bold")

    right = Text()
    right.append(f"{counterparty_label}: ", style="dim")
    right.append(record.get(counterparty_field) or "-", style="bold")
    addr = record.get("bill_to_address", "") or record.get("address", "")
    if addr:
        right.append(f"\n{addr}")

    grid.add_row(left, right)
    console.print(grid)
    console.print()

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    if record.get("number"):
        details.add_row("Number:", str(record["number"]))
    details.add_row("Date:", record.get("date", "-"))
    if record.get("due_date"):
        details.add_row("Due Date:", record["due_date"])
    if record.get("reference_number"):
        details.add_row("Reference:", record["reference_number"])
    if record.get("term_name"):
        details.add_row("Terms:", record["term_name"])
    if record.get("currency_iso_4217_code"):
        details.add_row("Currency:", record["currency_iso_4217_code"])
    console.print(details)
    console.print()

    items = record.get("items", [])
    if items:
        items_table = Table(show_lines=True, title="Line Items")
        items_table.add_column("#", justify="right", style="dim", width=4)
        items_table.add_column("Description", min_width=30)
        items_table.add_column("Qty", justify="right", width=10)
        items_table.add_column("Rate", justify="right", width=14)
        items_table.add_column("Amount", justify="right", width=14, style="bold")

        for i, item in enumerate(items, 1):
            qty = item.get("quantity", "1")
            rate = item.get("rate", "0")
            amount = _calc_line_amount(qty, rate)
            desc = item.get("memo") or f"Item #{item.get('item_id', i)}"
            items_table.add_row(str(i), desc, _fmt_decimal(qty), _money(rate, currency), _money(amount, currency))

        console.print(items_table)

    console.print()
    totals = Table.grid(padding=(0, 2))
    totals.add_column(min_width=40)
    totals.add_column(justify="right", style="dim", min_width=14)
    totals.add_column(justify="right", min_width=14)

    totals.add_row("", "Total:", _money(record.get("amount"), currency))
    paid = record.get("paid_total")
    if paid and paid != "0.00":
        totals.add_row("", "Paid:", f"-{_money(paid, currency)}")
    amount_due = record.get("amount_due")
    if amount_due is not None:
        totals.add_row("", "─" * 14, "─" * 14)
        totals.add_row("", Text("Amount Due:", style="bold"), Text(_money(amount_due, currency), style=f"bold {due_color}"))
    remaining = record.get("remaining_amount")
    if remaining is not None:
        totals.add_row("", "─" * 14, "─" * 14)
        totals.add_row("", Text("Remaining:", style="bold"), Text(_money(remaining, currency), style="bold"))

    console.print(totals)

    if record.get("memo"):
        console.print(f"\n[dim]Memo:[/dim] {record['memo']}")


# ── Invoice ──────────────────────────────────────────────────────────


def _invoice_list(items):
    _transaction_list(items, "Invoices", "Customer", "customer_name", show_due_date=True, show_paid=True, resource="invoice")


def _invoice_detail(r):
    _transaction_detail(r, "Invoice", "Customer", "customer_name", due_color="green", resource="invoice")


_register("invoice", _invoice_list, _invoice_detail)


# ── Bill ─────────────────────────────────────────────────────────────


def _bill_list(items):
    _transaction_list(items, "Bills", "Vendor", "vendor_name", show_due_date=True, show_paid=True, resource="bill")


def _bill_detail(r):
    _transaction_detail(r, "Bill", "Vendor", "vendor_name", due_color="red", resource="bill")


_register("bill", _bill_list, _bill_detail)


# ── Sales Order ──────────────────────────────────────────────────────


def _sales_order_list(items):
    _transaction_list(items, "Sales Orders", "Customer", "customer_name", resource="sales-order")


def _sales_order_detail(r):
    _transaction_detail(r, "Sales Order", "Customer", "customer_name", resource="sales-order")


_register("sales-order", _sales_order_list, _sales_order_detail)


# ── Purchase Order ───────────────────────────────────────────────────


def _purchase_order_list(items):
    _transaction_list(items, "Purchase Orders", "Vendor", "vendor_name", resource="purchase-order")


def _purchase_order_detail(r):
    _transaction_detail(r, "Purchase Order", "Vendor", "vendor_name", resource="purchase-order")


_register("purchase-order", _purchase_order_list, _purchase_order_detail)


# ── Cash Sale ────────────────────────────────────────────────────────


def _cash_sale_list(items):
    _transaction_list(items, "Cash Sales", "Customer", "customer_name", resource="cash-sale")


def _cash_sale_detail(r):
    _transaction_detail(r, "Cash Sale", "Customer", "customer_name", resource="cash-sale")


_register("cash-sale", _cash_sale_list, _cash_sale_detail)


# ── Direct Expense ───────────────────────────────────────────────────


def _direct_expense_list(items):
    _transaction_list(items, "Direct Expenses", "Vendor", "vendor_name", resource="direct-expense")


def _direct_expense_detail(r):
    _transaction_detail(r, "Direct Expense", "Vendor", "vendor_name", resource="direct-expense")


_register("direct-expense", _direct_expense_list, _direct_expense_detail)


# ── Customer Payments ────────────────────────────────────────────────


def _customer_payment_list(items):
    _transaction_list(items, "Customer Payments", "Customer", "customer_name", show_memo=True, resource="customer-payment")


def _customer_payment_detail(r):
    _transaction_detail(r, "Customer Payment", "Customer", "customer_name", resource="customer-payment")


_register("customer-payment", _customer_payment_list, _customer_payment_detail)


# ── Customer Credits ─────────────────────────────────────────────────


def _customer_credit_list(items):
    _transaction_list(items, "Customer Credits", "Customer", "customer_name", show_remaining=True, resource="customer-credit")


def _customer_credit_detail(r):
    _transaction_detail(r, "Customer Credit", "Customer", "customer_name", resource="customer-credit")


_register("customer-credit", _customer_credit_list, _customer_credit_detail)


# ── Customer Prepayments ─────────────────────────────────────────────


def _customer_prepayment_list(items):
    _transaction_list(items, "Customer Prepayments", "Customer", "customer_name", show_remaining=True, resource="customer-prepayment")


def _customer_prepayment_detail(r):
    _transaction_detail(r, "Customer Prepayment", "Customer", "customer_name", resource="customer-prepayment")


_register("customer-prepayment", _customer_prepayment_list, _customer_prepayment_detail)


# ── Customer Prepayment Applications ─────────────────────────────────


def _customer_prepayment_app_list(items):
    _transaction_list(items, "Customer Prepayment Applications", "Customer", "customer_name", resource="customer-prepayment-application")


def _customer_prepayment_app_detail(r):
    _transaction_detail(r, "Customer Prepayment Application", "Customer", "customer_name", resource="customer-prepayment-application")


_register("customer-prepayment-application", _customer_prepayment_app_list, _customer_prepayment_app_detail)


# ── Customer Deposits ────────────────────────────────────────────────


def _customer_deposit_list(items):
    _transaction_list(items, "Customer Deposits", "Customer", "customer_name", show_memo=True, resource="customer-deposit")


def _customer_deposit_detail(r):
    _transaction_detail(r, "Customer Deposit", "Customer", "customer_name", resource="customer-deposit")


_register("customer-deposit", _customer_deposit_list, _customer_deposit_detail)


# ── Customer Refunds ─────────────────────────────────────────────────


def _customer_refund_list(items):
    _transaction_list(items, "Customer Refunds", "Customer", "customer_name", resource="customer-refund")


def _customer_refund_detail(r):
    _transaction_detail(r, "Customer Refund", "Customer", "customer_name", resource="customer-refund")


_register("customer-refund", _customer_refund_list, _customer_refund_detail)


# ── Vendor Payments ──────────────────────────────────────────────────


def _vendor_payment_list(items):
    _transaction_list(items, "Vendor Payments", "Vendor", "vendor_name", show_memo=True, resource="vendor-payment")


def _vendor_payment_detail(r):
    _transaction_detail(r, "Vendor Payment", "Vendor", "vendor_name", resource="vendor-payment")


_register("vendor-payment", _vendor_payment_list, _vendor_payment_detail)


# ── Vendor Credits ───────────────────────────────────────────────────


def _vendor_credit_list(items):
    _transaction_list(items, "Vendor Credits", "Vendor", "vendor_name", show_remaining=True, resource="vendor-credit")


def _vendor_credit_detail(r):
    _transaction_detail(r, "Vendor Credit", "Vendor", "vendor_name", resource="vendor-credit")


_register("vendor-credit", _vendor_credit_list, _vendor_credit_detail)


# ── Vendor Prepayments ───────────────────────────────────────────────


def _vendor_prepayment_list(items):
    _transaction_list(items, "Vendor Prepayments", "Vendor", "vendor_name", show_remaining=True, resource="vendor-prepayment")


def _vendor_prepayment_detail(r):
    _transaction_detail(r, "Vendor Prepayment", "Vendor", "vendor_name", resource="vendor-prepayment")


_register("vendor-prepayment", _vendor_prepayment_list, _vendor_prepayment_detail)


# ── Vendor Prepayment Applications ───────────────────────────────────


def _vendor_prepayment_app_list(items):
    _transaction_list(items, "Vendor Prepayment Applications", "Vendor", "vendor_name", resource="vendor-prepayment-application")


def _vendor_prepayment_app_detail(r):
    _transaction_detail(r, "Vendor Prepayment Application", "Vendor", "vendor_name", resource="vendor-prepayment-application")


_register("vendor-prepayment-application", _vendor_prepayment_app_list, _vendor_prepayment_app_detail)


# ── Vendor Refunds ───────────────────────────────────────────────────


def _vendor_refund_list(items):
    _transaction_list(items, "Vendor Refunds", "Vendor", "vendor_name", resource="vendor-refund")


def _vendor_refund_detail(r):
    _transaction_detail(r, "Vendor Refund", "Vendor", "vendor_name", resource="vendor-refund")


_register("vendor-refund", _vendor_refund_list, _vendor_refund_detail)


# ── Journal Entry ────────────────────────────────────────────────────


def _journal_entry_list(items):
    _transaction_list(items, "Journal Entries", "Memo", "memo", resource="journal-entry")


def _journal_entry_detail(r):
    currency = r.get("currency_iso_4217_code") or r.get("company_currency", "")

    header = Text()
    header.append("JOURNAL ENTRY", style="bold")
    header.append(f"  {_fmt_id(r.get('internal_id'), 'journal-entry')}", style="bold cyan")
    status = r.get("record_status", "")
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("Date:", r.get("date", "-"))
    details.add_row("Company:", r.get("company_name", "-"))
    details.add_row("Currency:", currency or "-")
    if r.get("memo"):
        details.add_row("Memo:", r["memo"])
    console.print(details)
    console.print()

    items = r.get("items", [])
    if items:
        je_table = Table(show_lines=True, title="Entries")
        je_table.add_column("#", justify="right", style="dim", width=4)
        je_table.add_column("Account", min_width=25)
        je_table.add_column("Description", min_width=20)
        je_table.add_column("Debit", justify="right", width=14)
        je_table.add_column("Credit", justify="right", width=14)

        for i, item in enumerate(items, 1):
            account = item.get("account_name") or item.get("account_number") or item.get("account_id") or ""
            je_table.add_row(
                str(i),
                str(account),
                item.get("memo", ""),
                _money(item.get("debit"), currency) if item.get("debit") else "",
                _money(item.get("credit"), currency) if item.get("credit") else "",
            )

        console.print(je_table)


_register("journal-entry", _journal_entry_list, _journal_entry_detail)


# ── Intercompany Journal Entry ──────────────────────────────────────


def _ije_list(items):
    table = Table(title="Intercompany Journal Entries", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("#", style="bold", justify="right")
    table.add_column("Date", justify="center")
    table.add_column("Companies", min_width=20)
    table.add_column("Memo", max_width=20)
    table.add_column("Currency", justify="center")
    table.add_column("Amount", justify="right", style="bold")
    table.add_column("Status")

    for r in items:
        currency = r.get("currency_iso_4217_code", "")
        companies = r.get("companies", [])
        company_names = ", ".join(c.get("name", "") for c in companies) if companies else r.get("company_name", "-")
        memo = r.get("memo", "") or ""
        amount = sum(float(item.get("debit") or 0) for item in r.get("items", []))
        table.add_row(
            _fmt_id(r.get("internal_id"), "intercompany-journal-entry"),
            str(r.get("record_number", "")),
            r.get("date", "-"),
            company_names,
            memo[:20] + ("..." if len(memo) > 20 else ""),
            currency,
            _money(amount or r.get("amount"), currency),
            _status_badge(r.get("record_status", "")),
        )

    console.print(table)


def _ije_detail(r):
    currency = r.get("currency_iso_4217_code", "")

    header = Text()
    header.append("INTERCOMPANY JOURNAL ENTRY", style="bold")
    header.append(f"  {_fmt_id(r.get('internal_id'), 'intercompany-journal-entry')}", style="bold cyan")
    status = r.get("record_status", "")
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=20)
    details.add_column()
    details.add_row("Number:", str(r.get("record_number", "-")))
    details.add_row("Date:", r.get("date", "-"))
    tx_date = r.get("transaction_date")
    if tx_date and tx_date != r.get("date"):
        details.add_row("Transaction Date:", tx_date)
    companies = r.get("companies", [])
    if companies:
        details.add_row("Companies:", ", ".join(c.get("name", "") for c in companies))
    details.add_row("Currency:", currency or "-")
    exchange_rate = r.get("exchange_rate", "")
    if exchange_rate and exchange_rate not in ("1", "1.00", "1.00000000"):
        details.add_row("Exchange Rate:", exchange_rate)
    if r.get("memo"):
        details.add_row("Memo:", r["memo"])
    console.print(details)
    console.print()

    items = r.get("items", [])
    if items:
        items_sorted = sorted(items, key=lambda x: x.get("position", 0))
        je_table = Table(show_lines=True, title="Entries")
        je_table.add_column("#", justify="right", style="dim", width=4)
        je_table.add_column("Company", min_width=14)
        je_table.add_column("Account", min_width=20)
        je_table.add_column("Memo", min_width=16)
        je_table.add_column("Debit", justify="right", width=14)
        je_table.add_column("Credit", justify="right", width=14)
        je_table.add_column("Elim", justify="center", width=5)

        for i, item in enumerate(items_sorted, 1):
            account = item.get("account_name") or str(item.get("account_number", ""))
            elim = "\u2713" if item.get("eliminate") else ""
            je_table.add_row(
                str(i),
                item.get("company_name", "-"),
                account,
                item.get("memo", ""),
                _money(item.get("debit"), currency) if item.get("debit") else "",
                _money(item.get("credit"), currency) if item.get("credit") else "",
                elim,
            )

        console.print(je_table)


_register("intercompany-journal-entry", _ije_list, _ije_detail)


# ── Bank Transfer ────────────────────────────────────────────────────


def _bank_transfer_list(items):
    table = Table(title="Bank Transfers", show_lines=False)
    table.add_column("#", style="bold", justify="right")
    table.add_column("Date", justify="center")
    table.add_column("Company")
    table.add_column("From Account", min_width=14)
    table.add_column("Sent", justify="right")
    table.add_column("To Account", min_width=14)
    table.add_column("Received", justify="right")
    table.add_column("Status")

    for r in items:
        send_currency = r.get("credit_bank_account_currency", "")
        recv_currency = r.get("debit_bank_account_currency", "")
        table.add_row(
            _fmt_id(r.get("internal_id"), "bank-transfer"),
            r.get("date", "-"),
            r.get("company_name", "-"),
            r.get("credit_bank_account_name", "-"),
            _money(r.get("amount"), send_currency),
            r.get("debit_bank_account_name", "-"),
            _money(r.get("receiving_amount"), recv_currency),
            _status_badge(r.get("record_status", "")),
        )

    console.print(table)


def _bank_transfer_detail(r):
    header = Text()
    header.append("BANK TRANSFER", style="bold")
    header.append(f"  {_fmt_id(r.get('internal_id'), 'bank-transfer')}", style="bold cyan")
    status = r.get("record_status", "")
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=20)
    details.add_column()
    details.add_row("Date:", r.get("date", "-"))
    details.add_row("Company:", r.get("company_name", "-"))
    details.add_row("From:", r.get("credit_bank_account_name", "-"))
    details.add_row("Sending Amount:", _money(r.get("amount"), r.get("credit_bank_account_currency", "")))
    details.add_row("To:", r.get("debit_bank_account_name", "-"))
    details.add_row("Receiving Amount:", _money(r.get("receiving_amount"), r.get("debit_bank_account_currency", "")))
    if r.get("exchange_rate") and r["exchange_rate"] != "1":
        details.add_row("Exchange Rate:", r["exchange_rate"])
    if r.get("memo"):
        details.add_row("Memo:", r["memo"])
    console.print(details)


_register("bank-transfer", _bank_transfer_list, _bank_transfer_detail)


# ── Fixed Asset ──────────────────────────────────────────────────────


def _fixed_asset_list(items):
    table = Table(title="Fixed Assets", show_lines=False)
    table.add_column("#", style="bold", justify="right")
    table.add_column("Name", min_width=20)
    table.add_column("Company")
    table.add_column("Purchase Date", justify="center")
    table.add_column("Cost", justify="right", style="bold")
    table.add_column("Status")

    for r in items:
        table.add_row(
            _fmt_id(r.get("internal_id"), "fixed-asset"),
            r.get("name", "-"),
            r.get("company_name", "-"),
            r.get("purchase_date", "-"),
            _money(r.get("cost"), r.get("currency_iso_4217_code", "")),
            _status_badge(r.get("record_status", r.get("status", ""))),
        )

    console.print(table)


def _fixed_asset_detail(r):
    header = Text()
    header.append("FIXED ASSET", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    status = r.get("record_status", r.get("status", ""))
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=20)
    details.add_column()
    details.add_row("Number:", str(r.get("number", "-")))
    details.add_row("Company:", r.get("company_name", "-"))
    details.add_row("Purchase Date:", r.get("purchase_date", "-"))
    details.add_row("Cost:", _money(r.get("cost"), r.get("currency_iso_4217_code", "")))
    if r.get("serial_number"):
        details.add_row("Serial Number:", r["serial_number"])
    if r.get("memo"):
        details.add_row("Description:", r["memo"])
    console.print(details)


_register("fixed-asset", _fixed_asset_list, _fixed_asset_detail)


# ── Customer ─────────────────────────────────────────────────────────


def _customer_list(items):
    table = Table(title="Customers", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Type")
    table.add_column("Email")
    table.add_column("Phone")
    table.add_column("Status")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("name", "-"),
            r.get("customer_type", "-"),
            r.get("email", "-"),
            r.get("phone", "-"),
            _status_badge(r.get("record_status", "")),
        )

    console.print(table)


def _customer_detail(r):
    header = Text()
    header.append("CUSTOMER", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Type:", r.get("customer_type", "-"))
    if r.get("email"):
        details.add_row("Email:", r["email"])
    if r.get("phone"):
        details.add_row("Phone:", r["phone"])
    if r.get("website"):
        details.add_row("Website:", r["website"])
    if r.get("parent_name"):
        details.add_row("Parent:", r["parent_name"])
    console.print(details)


_register("customer", _customer_list, _customer_detail)


# ── Vendor ───────────────────────────────────────────────────────────


def _vendor_list(items):
    table = Table(title="Vendors", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Type")
    table.add_column("Email")
    table.add_column("Phone")
    table.add_column("Status")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("name", "-"),
            r.get("vendor_type", "-"),
            r.get("email", "-"),
            r.get("phone", "-"),
            _status_badge(r.get("record_status", "")),
        )

    console.print(table)


def _vendor_detail(r):
    header = Text()
    header.append("VENDOR", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Type:", r.get("vendor_type", "-"))
    if r.get("email"):
        details.add_row("Email:", r["email"])
    if r.get("phone"):
        details.add_row("Phone:", r["phone"])
    if r.get("website"):
        details.add_row("Website:", r["website"])
    console.print(details)


_register("vendor", _vendor_list, _vendor_detail)


# ── Item ─────────────────────────────────────────────────────────────


def _item_list(items):
    table = Table(title="Items", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("SKU")
    table.add_column("Type")
    table.add_column("Expense Account")
    table.add_column("Income Account")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("name", "-"),
            r.get("sku", "-"),
            r.get("item_type", "-"),
            str(r.get("expense_account_id", "-")),
            str(r.get("income_account_id", "-")),
        )

    console.print(table)


def _item_detail(r):
    header = Text()
    header.append("ITEM", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=18)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("SKU:", r.get("sku", "-"))
    details.add_row("Type:", r.get("item_type", "-"))
    if r.get("expense_account_id"):
        details.add_row("Expense Account:", str(r["expense_account_id"]))
    if r.get("income_account_id"):
        details.add_row("Income Account:", str(r["income_account_id"]))
    if r.get("description"):
        details.add_row("Description:", r["description"])
    console.print(details)


_register("item", _item_list, _item_detail)


# ── Account ──────────────────────────────────────────────────────────


def _account_list(items):
    table = Table(title="Chart of Accounts", show_lines=False)
    table.add_column("Number", justify="right", style="bold")
    table.add_column("Name", min_width=28)
    table.add_column("Type")
    table.add_column("Description", max_width=30)
    table.add_column("Active")

    for r in items:
        active = "[green]active[/green]" if r.get("is_active", True) else "[dim]inactive[/dim]"
        desc = r.get("description", "") or ""
        table.add_row(
            str(r.get("number", "")),
            r.get("name", "-"),
            r.get("account_type", "-"),
            desc[:30] + ("..." if len(desc) > 30 else ""),
            active,
        )

    console.print(table)


def _account_detail(r):
    header = Text()
    header.append("ACCOUNT", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("Number:", str(r.get("number", "-")))
    details.add_row("Type:", r.get("account_type", "-"))
    details.add_row("Currency:", r.get("currency_iso_4217_code", "-"))
    if r.get("description"):
        details.add_row("Description:", r["description"])
    active = "Active" if r.get("is_active", True) else "Inactive"
    details.add_row("Status:", active)
    console.print(details)


_register("account", _account_list, _account_detail)


# ── Company ──────────────────────────────────────────────────────────


def _company_list(items):
    table = Table(title="Companies", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Currency")
    table.add_column("Country")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("name", "-"),
            r.get("currency_iso_4217_code", "-"),
            r.get("country", "-"),
        )

    console.print(table)


def _company_detail(r):
    header = Text()
    header.append("COMPANY", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Currency:", r.get("currency_iso_4217_code", "-"))
    if r.get("country"):
        details.add_row("Country:", r["country"])
    console.print(details)


_register("company", _company_list, _company_detail)


# ── Contract ─────────────────────────────────────────────────────────


def _contract_list(items):
    table = Table(title="Contracts", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("#", style="bold", justify="right")
    table.add_column("Name", min_width=20)
    table.add_column("Customer")
    table.add_column("Start", justify="center")
    table.add_column("End", justify="center")
    table.add_column("Currency")
    table.add_column("Status")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            str(r.get("number", r.get("id", ""))),
            r.get("name", "-"),
            r.get("customer_name", "-"),
            r.get("start_date", "-"),
            r.get("end_date", "-"),
            r.get("currency_iso_4217_code", "-"),
            _status_badge(r.get("status", "")),
        )

    console.print(table)


def _contract_detail(r):
    header = Text()
    header.append("CONTRACT", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    status = r.get("status", "")
    if status:
        header.append(f"  {status.upper()}", style=_status_color(status))
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Customer:", r.get("customer_name", "-"))
    details.add_row("Company:", r.get("company_name", "-"))
    details.add_row("Start Date:", r.get("start_date", "-"))
    details.add_row("End Date:", r.get("end_date", "-"))
    details.add_row("Currency:", r.get("currency_iso_4217_code", "-"))
    console.print(details)


_register("contract", _contract_list, _contract_detail)


# ── Budget ───────────────────────────────────────────────────────────


def _budget_list(items):
    table = Table(title="Budgets", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Company")
    table.add_column("Start", justify="center")
    table.add_column("End", justify="center")

    for r in items:
        table.add_row(
            str(r.get("id", "")),
            r.get("name", "-"),
            r.get("company_name", "-"),
            r.get("start_date", "-"),
            r.get("end_date", "-"),
        )

    console.print(table)


def _budget_detail(r):
    header = Text()
    header.append("BUDGET", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Company:", r.get("company_name", "-"))
    details.add_row("Start:", r.get("start_date", "-"))
    details.add_row("End:", r.get("end_date", "-"))
    console.print(details)


_register("budget", _budget_list, _budget_detail)


# ── Classification ───────────────────────────────────────────────────


def _classification_list(items):
    table = Table(title="Classifications", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")

    for r in items:
        table.add_row(str(r.get("id", "")), r.get("name", "-"))

    console.print(table)


def _classification_detail(r):
    header = Text()
    header.append("CLASSIFICATION", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Name:", r.get("name", "-"))
    console.print(details)


_register("classification", _classification_list, _classification_detail)


# ── Depreciation Book ────────────────────────────────────────────────


def _depreciation_book_list(items):
    table = Table(title="Depreciation Books", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Method")

    for r in items:
        table.add_row(str(r.get("id", "")), r.get("name", "-"), r.get("method", "-"))

    console.print(table)


def _depreciation_book_detail(r):
    header = Text()
    header.append("DEPRECIATION BOOK", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Name:", r.get("name", "-"))
    details.add_row("Method:", r.get("method", "-"))
    console.print(details)


_register("depreciation-book", _depreciation_book_list, _depreciation_book_detail)


# ── Workflow ─────────────────────────────────────────────────────────


def _workflow_list(items):
    table = Table(title="Workflows", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name", min_width=24, style="bold")
    table.add_column("Status")

    for r in items:
        table.add_row(str(r.get("id", "")), r.get("name", "-"), _status_badge(r.get("status", "")))

    console.print(table)


def _workflow_detail(r):
    header = Text()
    header.append("WORKFLOW", style="bold")
    header.append(f"  {r.get('name', '')}", style="bold cyan")
    console.print(Panel(header, expand=False))

    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", min_width=16)
    details.add_column()
    details.add_row("ID:", str(r.get("id", "-")))
    details.add_row("Name:", r.get("name", "-"))
    console.print(details)


_register("workflow", _workflow_list, _workflow_detail)


# ── Recurring records (use generic transaction pattern) ──────────────

for _prefix in ("recurring-invoice", "recurring-bill", "recurring-journal-entry"):
    _register(_prefix, None, None)  # falls back to generic


# ── Generic fallback ─────────────────────────────────────────────────


def _print_generic_list(items: list[dict]) -> None:
    if not items:
        console.print("No results.")
        return
    table = Table()
    # Pick useful columns: skip nested objects and long fields
    columns = [k for k in items[0] if not isinstance(items[0][k], (dict, list))][:12]
    for col in columns:
        table.add_column(col)
    for item in items:
        table.add_row(*[str(item.get(col, ""))[:40] for col in columns])
    console.print(table)


def _print_generic_detail(item: dict) -> None:
    table = Table(show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, value in item.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        table.add_row(key, str(value)[:100])
    console.print(table)


# ── Helpers ──────────────────────────────────────────────────────────


def _money(value, currency: str = "") -> str:
    if value is None:
        return "-"
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    symbol = _currency_symbol(currency)
    return f"{symbol}{num:,.2f}"


def _currency_symbol(code: str) -> str:
    symbols = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "CAD": "CA$", "AUD": "A$"}
    return symbols.get(code, f"{code} " if code else "")


def _fmt_decimal(value) -> str:
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    if num == int(num):
        return str(int(num))
    return f"{num:.2f}"


def _calc_line_amount(qty, rate) -> str:
    try:
        return f"{float(qty) * float(rate):.2f}"
    except (ValueError, TypeError):
        return "0.00"


def _status_color(status: str) -> str:
    return {"draft": "yellow", "posted": "green", "archived": "dim", "active": "green", "inactive": "dim"}.get(status, "white")


def _status_badge(status: str) -> str:
    if not status:
        return "-"
    color = _status_color(status)
    return f"[{color}]{status}[/{color}]"
