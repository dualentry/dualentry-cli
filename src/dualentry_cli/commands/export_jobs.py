"""On-demand destination data export jobs (Snowflake / warehouse refresh)."""

from __future__ import annotations

import time
from enum import StrEnum

import typer

from dualentry_cli.commands import AllPages, Format, Limit, Offset
from dualentry_cli.commands.actions import make_action_app, run_get, run_list
from dualentry_cli.output import format_output

_TERMINAL = frozenset({"completed", "failed"})


class ExportJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


app = make_action_app("Manage Snowflake / warehouse export jobs")


@app.command("create")
def create_export_job(
    integration_id: int | None = typer.Option(
        None,
        "--integration-id",
        help="Destination integration ID. Optional when the org has exactly one connected destination.",
    ),
    output: str = Format,
):
    """
    Request an off-cycle data export refresh.

    DualEntry accepts the request and starts the export when capacity allows.
    Calling this while an export is already running returns that job with
    deduplicated=true instead of starting a second one.
    """
    from dualentry_cli.main import get_client

    body: dict = {}
    if integration_id is not None:
        body["integration_id"] = integration_id

    data = get_client().post("/export-jobs/", json=body or None)

    if output == "json":
        format_output(data, resource="export-job", fmt="json")
        return

    if data.get("deduplicated"):
        typer.secho(
            "An export was already running; returning that job (deduplicated).",
            fg=typer.colors.YELLOW,
            err=True,
        )
    job = data.get("job") or data
    format_output(job, resource="export-job", fmt=output)


@app.command("list")
def list_export_jobs(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    status: list[ExportJobStatus] | None = typer.Option(
        None,
        "--status",
        help="Filter by status: pending, running, completed, or failed. Repeatable.",
    ),
    output: str = Format,
):
    """List destination data export jobs, most recent first."""
    statuses = [s.value for s in status] if status else None
    run_list(
        "export-jobs",
        resource="export-job",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        status=statuses,
        status_param="status",
    )


@app.command("get")
def get_export_job(
    job_id: int = typer.Argument(help="Export job ID from create or list"),
    output: str = Format,
):
    """Get one export job by ID. Poll this after create."""
    run_get(f"/export-jobs/{job_id}/", resource="export-job", output=output)


@app.command("wait")
def wait_export_job(
    job_id: int = typer.Argument(help="Export job ID to poll until finished"),
    interval: float = typer.Option(
        5.0,
        "--interval",
        min=0.5,
        help="Seconds between status polls",
    ),
    timeout: float = typer.Option(
        1800.0,
        "--timeout",
        min=1.0,
        help="Give up after this many seconds (default 30 minutes)",
    ),
    output: str = Format,
):
    """
    Poll an export job until it completes or fails.

    Exit 0 when status is completed, 1 when failed or the timeout elapses.
    Useful in CI after create.
    """
    from dualentry_cli.main import get_client

    client = get_client()
    deadline = time.monotonic() + timeout
    job: dict = {}

    while True:
        job = client.get(f"/export-jobs/{job_id}/")
        status = job.get("status")
        if status in _TERMINAL:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            typer.secho(
                f"Timed out after {timeout:.0f}s waiting for export job {job_id} (last status: {status}).",
                fg=typer.colors.RED,
                err=True,
            )
            format_output(job, resource="export-job", fmt=output)
            raise typer.Exit(code=1)
        typer.secho(
            f"export-jobs wait: job {job_id} is {status}; next poll in {min(interval, remaining):.0f}s ({remaining:.0f}s left)",
            err=True,
        )
        time.sleep(min(interval, remaining))

    format_output(job, resource="export-job", fmt=output)
    if job.get("status") == "failed":
        raise typer.Exit(code=1)
