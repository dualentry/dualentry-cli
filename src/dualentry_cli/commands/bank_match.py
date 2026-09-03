"""Bank-match commands."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer

from dualentry_cli.commands import AllPages, Format, Limit, Offset
from dualentry_cli.commands.actions import load_json_file, make_action_app, run_get, run_list, run_post

app = make_action_app("Manage bank matches")
suggestions_app = make_action_app("Manage bank-match suggestions")
transactions_app = make_action_app("Manage bank transactions")
app.add_typer(suggestions_app, name="suggestions")
app.add_typer(transactions_app, name="bank-transactions")


@app.command("status-counts")
def status_counts(output: str = Format):
    """
    Show bank-match processing counts.

    See how many bank rows sit in each pipeline stage.
    Work is still running while unprocessed, awaiting_ai, or ai_in_progress
    is non-zero.
    """
    run_get("/bank-match/status-counts/", resource="bank-match", output=output)


@suggestions_app.command("list")
def list_suggestions(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    financial_transaction_id: int | None = typer.Option(
        None,
        "--financial-transaction-id",
        help="Limit to candidates for one bank-feed row ID",
    ),
    suggestion_type: str | None = typer.Option(
        None,
        "--suggestion-type",
        help="Suggestion kind: match (existing transaction) or create (draft new)",
    ),
    highest_ranked: bool = typer.Option(
        False,
        "--highest-ranked",
        help="Return only the top pick per bank row (same default as the UI)",
    ),
    output: str = Format,
):
    """
    List bank-match suggestions.

    Each suggestion pairs a bank-feed row with a DualEntry transaction.
    """
    run_list(
        "bank-match/suggestions",
        resource="bank-match-suggestion",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        financial_transaction_id=financial_transaction_id,
        suggestion_type=suggestion_type,
        is_highest_ranked=True if highest_ranked else None,
    )


@suggestions_app.command("get")
def get_suggestion(
    suggestion_id: int = typer.Argument(help="Suggestion ID from suggestions list"),
    output: str = Format,
):
    """Get one bank-match suggestion by ID."""
    run_get(f"/bank-match/suggestions/{suggestion_id}/", resource="bank-match-suggestion", output=output)


@transactions_app.command("list")
def list_bank_transactions(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    financial_account_id: int | None = typer.Option(
        None,
        "--financial-account-id",
        help="Limit to one connected bank or credit-card account ID",
    ),
    matching_status: str | None = typer.Option(
        None,
        "--matching-status",
        help="Pipeline stage, e.g. unprocessed, ai_suggested, matched, no_match, excluded",
    ),
    date_from: datetime | None = typer.Option(
        None,
        "--date-from",
        help="Inclusive lower bound on transaction date (YYYY-MM-DD)",
    ),
    date_to: datetime | None = typer.Option(
        None,
        "--date-to",
        help="Inclusive upper bound on transaction date (YYYY-MM-DD)",
    ),
    is_posted: bool | None = typer.Option(
        None,
        "--is-posted/--not-posted",
        help="Posted-only (--is-posted) or pending-only (--not-posted); omit for both",
    ),
    include_expired: bool = typer.Option(
        False,
        "--include-expired",
        help="Include expired bank-feed rows (hidden by default)",
    ),
    output: str = Format,
):
    """
    List bank-feed transactions.

    Page through bank rows, decide DualEntry targets, then run match.
    """
    run_list(
        "bank-match/bank-transactions",
        resource="bank-transaction",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        financial_account_id=financial_account_id,
        matching_status=matching_status,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        is_posted=is_posted,
        include_expired=True if include_expired else None,
    )


@transactions_app.command("get")
def get_bank_transaction(
    financial_transaction_id: int = typer.Argument(help="Bank-feed transaction ID from bank-transactions list"),
    output: str = Format,
):
    """Get one bank-feed transaction by ID."""
    run_get(
        f"/bank-match/bank-transactions/{financial_transaction_id}/",
        resource="bank-transaction",
        output=output,
    )


@app.command("match")
def match(
    file: Path | None = typer.Option(
        None,
        "--file",
        "-f",
        help="JSON file with full match body (supports 1:1 and M:N). Cannot combine with ID flags",
    ),
    financial_transaction_id: int | None = typer.Option(
        None,
        "--financial-transaction-id",
        help="Bank-feed row ID to match (1:1). Required when --file is omitted",
    ),
    transaction_id: int | None = typer.Option(
        None,
        "--transaction-id",
        help="DualEntry transaction ID to pair with (1:1). Use this or --entry-id, not both",
    ),
    entry_id: int | None = typer.Option(
        None,
        "--entry-id",
        help="DualEntry entry ID for a partial match (1:1). Use this or --transaction-id, not both",
    ),
    output: str = Format,
):
    """
    Confirm a bank match.

    Provide either --file with the API JSON body, or a 1:1 match via
    --financial-transaction-id plus exactly one of --transaction-id or
    --entry-id.
    """
    if file:
        if any(value is not None for value in (financial_transaction_id, transaction_id, entry_id)):
            raise typer.BadParameter("--file cannot be combined with match ID options")
        body = load_json_file(file)
    else:
        if financial_transaction_id is None:
            raise typer.BadParameter("provide --file or --financial-transaction-id")
        if (transaction_id is None) == (entry_id is None):
            raise typer.BadParameter("provide exactly one of --transaction-id or --entry-id")
        body = {"financial_transaction_id": financial_transaction_id}
        body["transaction_id" if transaction_id is not None else "entry_id"] = transaction_id or entry_id
    run_post("/bank-match/matches/", resource="bank-match", output=output, body=body)


_TEMPLATE_1_1 = {"financial_transaction_id": 10, "transaction_id": 20}
_TEMPLATE_M_N = {"financial_transaction_ids": [10, 11], "transaction_ids": [20, 21]}
_TEMPLATE_PARTIAL = {"financial_transaction_id": 10, "entry_id": 20}


@app.command("template")
def template_cmd(
    output_file: Path | None = typer.Option(None, "--output", "-o", help="Write template to file instead of stdout"),
    type: str = typer.Option("1:1", "--type", "-t", help='Type of template. valid values are "1:1", "m:n", "partial"'),
):
    """Output a sample bank match JSON template."""
    if type == "1:1":
        template = _TEMPLATE_1_1
    elif type == "m:n":
        template = _TEMPLATE_M_N
    elif type == "partial":
        template = _TEMPLATE_PARTIAL
    else:
        raise typer.BadParameter(f"Unknown template type: {type}")

    content = json.dumps(template, indent=2)
    if output_file:
        output_file.write_text(content + "\n")
        typer.secho(f"Template written to {output_file}", fg=typer.colors.GREEN)
    else:
        typer.echo(content)


@app.command("unmatch")
def unmatch(
    financial_transaction_id: int | None = typer.Option(
        None,
        "--financial-transaction-id",
        help="Bank-feed row ID in the match group to undo. Provide this or --match-group-id",
    ),
    match_group_id: int | None = typer.Option(
        None,
        "--match-group-id",
        help="Match group ID from a prior match response. Provide this or --financial-transaction-id",
    ),
    output: str = Format,
):
    """
    Undo a bank match.

    Provide exactly one of --financial-transaction-id or --match-group-id.
    Unmatching any member dissolves the whole group.
    """
    if (financial_transaction_id is None) == (match_group_id is None):
        raise typer.BadParameter("provide exactly one of --financial-transaction-id or --match-group-id")
    body = {"financial_transaction_id": financial_transaction_id} if financial_transaction_id is not None else {"match_group_id": match_group_id}
    run_post("/bank-match/unmatches/", resource="bank-match", output=output, body=body)
