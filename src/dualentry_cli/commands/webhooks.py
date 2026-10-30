"""
Webhook commands: register endpoints, choose topics, and read delivery history.

Webhooks are addressed by UUID, not by a record number, and `/topics/` returns a
bare list rather than a page, so these commands are hand-written instead of
coming from the resource factory.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

import typer
from typer._click.exceptions import UsageError

from dualentry_cli.cli import HelpfulGroup
from dualentry_cli.commands import AllPages, Format, Limit, Offset, ResumeFlag, Search, _warn_all_truncated
from dualentry_cli.commands.actions import run_get, run_list
from dualentry_cli.output import WebhookTopic, format_output

app = typer.Typer(help="Manage webhooks that send DualEntry events to your endpoint", no_args_is_help=True, cls=HelpfulGroup)

WebhookId = typer.Argument(help="Webhook UUID, from `dualentry webhooks list`")
Topics = typer.Option(
    None,
    "--topic",
    "-t",
    help="Topic to subscribe to; repeat for several. See `dualentry webhooks topics`.",
)

# Every `list` filter, so the --all resume hint repeats all of them.
_LIST_RESUME_FLAGS: dict[str, ResumeFlag] = {
    "search": "--search",
    "is_active": ("--active", "--inactive"),
}


def _warn_if_no_topics(topics: Sequence[str]) -> None:
    """Deliveries only go to webhooks subscribed to the event's topic, so none means silence."""
    if not topics:
        typer.secho(
            "Warning: this webhook has no topics, so it will receive no events. Add some with `dualentry webhooks update --topic`.",
            fg=typer.colors.YELLOW,
            err=True,
        )


@app.command("topics")
def topics_cmd(output: str = Format) -> None:
    """List the topics a webhook can subscribe to, one per line."""
    from dualentry_cli.main import get_client

    # A bare list, not a page, though get() is annotated for the usual dict.
    names = cast("list[WebhookTopic]", get_client().get("/webhooks/topics/"))
    if output == "json":
        # format_output is typed for dicts; print the API's list as-is instead.
        print(json.dumps(names, indent=2))
        return
    for topic in names:
        typer.echo(topic["name"])


@app.command("list")
def list_cmd(
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    search: str | None = Search,
    active: bool | None = typer.Option(None, "--active/--inactive", help="Only active or only inactive webhooks [default: both]"),
    output: str = Format,
) -> None:
    """List webhooks, newest first."""
    run_list(
        "webhooks",
        resource="webhook",
        limit=limit,
        offset=offset,
        all_pages=all_pages,
        output=output,
        resume_flags=_LIST_RESUME_FLAGS,
        search=search,
        is_active=active,
    )


@app.command("get")
def get_cmd(webhook_id: UUID = WebhookId, output: str = Format) -> None:
    """Get one webhook, including whether it was auto-disabled and why."""
    run_get(f"/webhooks/{webhook_id}/", resource="webhook", output=output)


@app.command("create")
def create_cmd(
    url: str = typer.Option(..., "--url", help="Public http(s) URL that will receive the events; use https in production"),
    topics: list[str] | None = Topics,
    output: str = Format,
) -> None:
    """
    Register a webhook endpoint.

    The response includes the signing secret. It is shown once and never again.
    """
    from dualentry_cli.main import get_client

    chosen = topics or []
    data = get_client().post("/webhooks/", json={"url": url, "topics": chosen})
    format_output(data, resource="webhook", fmt=output)
    _warn_if_no_topics(chosen)


@app.command("update")
def update_cmd(
    webhook_id: UUID = WebhookId,
    url: str | None = typer.Option(None, "--url", help="New endpoint URL"),
    topics: list[str] | None = Topics,
    clear_topics: bool = typer.Option(False, "--clear-topics", help="Unsubscribe from every topic"),
    active: bool | None = typer.Option(
        None,
        "--active/--inactive",
        help="Turn delivery on or off. --active also clears an auto-disable after repeated failures.",
    ),
    output: str = Format,
) -> None:
    """
    Change a webhook. Only the options you pass are changed.

    --topic replaces the whole subscription list; it does not add to it.
    """
    from dualentry_cli.main import get_client

    if topics and clear_topics:
        raise typer.BadParameter("pass --topic or --clear-topics, not both", param_hint="'--clear-topics'")

    body: dict[str, Any] = {}
    if url is not None:
        body["url"] = url
    if topics:
        body["topics"] = topics
    elif clear_topics:
        body["topics"] = []
    if active is not None:
        body["is_active"] = active
    if not body:
        raise UsageError("nothing to change; pass --url, --topic, --clear-topics, --active, or --inactive")

    # PATCH: the API's PUT takes the same optional fields, so it adds nothing here.
    data = get_client().patch(f"/webhooks/{webhook_id}/", json=body)
    format_output(data, resource="webhook", fmt=output)
    if "topics" in body:
        _warn_if_no_topics(body["topics"])


@app.command("delete")
def delete_cmd(webhook_id: UUID = WebhookId) -> None:
    """Delete a webhook. Its delivery history, including pending deliveries, is deleted too."""
    from dualentry_cli.main import get_client

    get_client().delete(f"/webhooks/{webhook_id}/")
    typer.echo(f"Webhook {webhook_id} deleted, with its delivery history.")


@app.command("deliveries")
def deliveries_cmd(
    webhook_id: UUID = WebhookId,
    limit: int = Limit,
    offset: int = Offset,
    all_pages: bool = AllPages,
    output: str = Format,
) -> None:
    """List a webhook's delivery attempts, newest first, with status and last error."""
    from dualentry_cli.main import get_client

    path = f"/webhooks/{webhook_id}/deliveries/"
    client = get_client()
    if not all_pages:
        format_output(client.get(path, params={"limit": limit, "offset": offset}), resource="webhook-delivery", fmt=output)
        return

    data = client.paginate(path, start_offset=offset)
    next_offset = data.pop("next_offset", None)
    format_output(data, resource="webhook-delivery", fmt=output)
    if next_offset is not None:
        # The shared hint rebuilds the command from the API path, which would give
        # `webhooks <uuid> deliveries list`; this command's shape needs its own.
        _warn_all_truncated(
            path,
            fetched_through=next_offset,
            total=data["count"],
            next_offset=next_offset,
            filters={},
            resume=shlex.join(["dualentry", "webhooks", "deliveries", str(webhook_id), "--all", "--offset", str(next_offset)]),
        )
