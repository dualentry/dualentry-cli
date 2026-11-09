from __future__ import annotations

from datetime import datetime
from enum import StrEnum

import typer

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, Format, Limit, Offset, ResumeFlag
from dualentry_cli.commands.actions import run_get, run_list

app = typer.Typer(help="Look up GST tax rates (AU, NZ, SG, IN, CA GST and MY SST)", no_args_is_help=True, cls=HelpfulGroup)

_LIST_RESUME_FLAGS: dict[str, ResumeFlag] = {
    "country_code": "--country",
    "tax_treatment": "--treatment",
    "is_active": ("--active", "--inactive"),
    "updated_after": "--updated-after",
    "updated_before": "--updated-before",
}


# Mirrors the API's country and treatment enums, so a typo fails here with the valid
# choices listed, rather than as a 422 from the server. test_integration.py checks
# these against the API's published OpenAPI schema, so drift fails a test.
class GstCountry(StrEnum):
    AU = "AU"
    NZ = "NZ"
    SG = "SG"
    IN = "IN"
    CA = "CA"
    MY = "MY"


class GstTreatment(StrEnum):
    STANDARD = "STANDARD"
    ZERO_RATED = "ZERO_RATED"
    EXEMPT = "EXEMPT"
    IMPORT_GST = "IMPORT_GST"
    REVERSE_CHARGE = "REVERSE_CHARGE"
    SELF_ASSESSED = "SELF_ASSESSED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


def _aware_timestamp(value: str | None) -> str | None:
    """Reject naive or malformed `--updated-*` values before the API sees them."""
    if value is None:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter(f"expected an ISO 8601 timestamp such as 2026-10-01T00:00:00Z, got {value!r}") from e
    if moment.tzinfo is None:
        raise typer.BadParameter(f"{value!r} has no timezone; add Z or an offset such as +10:00")
    return value


@app.command("list")
def list_cmd(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    country: list[GstCountry] | None = typer.Option(None, "--country", case_sensitive=False, help="Filter by country; repeat for several"),
    treatment: GstTreatment | None = typer.Option(None, "--treatment", case_sensitive=False, help="Filter by tax treatment"),
    active: bool | None = typer.Option(None, "--active/--inactive", help="Only active or only inactive rates [default: both]"),
    updated_after: str | None = typer.Option(
        None, "--updated-after", callback=_aware_timestamp, metavar="<timestamp>", help="Updated at or after this ISO 8601 timestamp (with timezone)"
    ),
    updated_before: str | None = typer.Option(
        None, "--updated-before", callback=_aware_timestamp, metavar="<timestamp>", help="Updated at or before this ISO 8601 timestamp (with timezone)"
    ),
    output: str = Format,
) -> None:
    """List GST tax rates. Use a rate's ID as `gst_tax_rate_id` on line items."""
    run_list(
        "gst-tax-rates",
        resource="gst-tax-rate",
        resume_flags=_LIST_RESUME_FLAGS,
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        country_code=[c.value for c in country] if country else None,
        tax_treatment=treatment.value if treatment else None,
        is_active=active,
        updated_after=updated_after,
        updated_before=updated_before,
    )


@app.command("get")
def get_cmd(
    rate_id: int = typer.Argument(help="GST tax rate ID"),
    output: str = Format,
) -> None:
    """Get a GST tax rate, with its component breakdown for split rates."""
    run_get(f"/gst-tax-rates/{rate_id}/", resource="gst-tax-rate", output=output)
