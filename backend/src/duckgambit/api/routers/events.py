"""The event log over HTTP (ADR-0002): a pollable JSON page and the same data as SSE."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from duckgambit.api.deps import Services
from duckgambit.api.schemas.base import StreamName
from duckgambit.api.schemas.events import EVENT_ADAPTER, EventPage, to_wire

router = APIRouter(prefix="/events", tags=["events"])

Deps = Annotated[Services, Depends()]
Streams = Annotated[
    list[StreamName],
    Query(alias="stream", min_length=1, max_length=20, description="e.g. match:mat_123"),
]
KEEPALIVE_SECONDS = 15.0


@router.get("", operation_id="readEvents")
async def read_events(
    services: Deps,
    streams: Streams,
    after: Annotated[int, Query(ge=0, description="Return events with a cursor above this")] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> EventPage:
    """A page of events, oldest first. Works for replay and for clients that cannot stream."""
    envelopes = await services.events.read(streams, after, limit)
    return EventPage(
        events=[to_wire(envelope) for envelope in envelopes],
        next_cursor=envelopes[-1].cursor if envelopes else after,
    )


@router.get(
    "/stream",
    operation_id="streamEvents",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "Server-sent events. Each message has `id` (the cursor), `event` (the type) and "
                "`data` (one EventEnvelope as JSON)."
            ),
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def stream_events(
    request: Request,
    services: Deps,
    streams: Streams,
    after: Annotated[int, Query(ge=0)] = 0,
    follow: Annotated[
        bool, Query(description="false: send what exists and close; true: keep the stream open")
    ] = True,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """The same events as `readEvents`, pushed as they happen. Reconnecting resumes exactly."""
    cursor = after
    if last_event_id is not None and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    events = services.events

    async def body() -> AsyncIterator[bytes]:
        nonlocal cursor
        yield b": connected\n\n"
        while True:
            seen = events.version
            batch = await events.read(streams, cursor, 200)
            for envelope in batch:
                payload = EVENT_ADAPTER.dump_json(to_wire(envelope), by_alias=True).decode()
                yield f"id: {envelope.cursor}\nevent: {envelope.type}\ndata: {payload}\n\n".encode()
                cursor = envelope.cursor
            if batch:
                continue
            if not follow or events.closed or await request.is_disconnected():
                return
            if not await events.wait(seen, KEEPALIVE_SECONDS):
                yield b": keepalive\n\n"

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
