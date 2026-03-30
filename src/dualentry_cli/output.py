"""Output formatting for DualEntry CLI."""
from __future__ import annotations
import json
from rich.console import Console
from rich.table import Table

console = Console()

def format_output(data: dict, fmt: str = "table") -> None:
    if fmt == "json":
        print(json.dumps(data, indent=2))
        return
    if "items" in data:
        _print_table(data["items"])
        if "count" in data:
            console.print(f"\nTotal: {data['count']}")
        return
    _print_single(data)

def _print_table(items: list[dict]) -> None:
    if not items:
        console.print("No results.")
        return
    table = Table()
    columns = list(items[0].keys())
    for col in columns:
        table.add_column(col)
    for item in items:
        table.add_row(*[str(item.get(col, "")) for col in columns])
    console.print(table)

def _print_single(item: dict) -> None:
    table = Table(show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, value in item.items():
        table.add_row(key, str(value))
    console.print(table)
