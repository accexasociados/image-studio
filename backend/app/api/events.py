import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.events import SQLiteEventStore, get_event_store

router = APIRouter(tags=["events"])
EventStoreDep = Annotated[SQLiteEventStore, Depends(get_event_store)]


class DisconnectChecker(Protocol):
    async def is_disconnected(self) -> bool: ...


def _cursor(after_id: int | None, last_event_id: str | None) -> int:
    if after_id is not None:
        return after_id
    if last_event_id is None:
        return 0
    try:
        parsed = int(last_event_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Last-Event-ID debe ser un entero no negativo.",
        ) from None
    if parsed < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Last-Event-ID debe ser un entero no negativo.",
        )
    return parsed


def _sse_frame(event_id: int, event_type: str, data: dict[str, object]) -> str:
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event_type}\ndata: {serialized}\n\n"


async def event_stream(
    request: DisconnectChecker,
    store: SQLiteEventStore,
    *,
    after_id: int,
    poll_seconds: float = 0.5,
    heartbeat_seconds: float = 15.0,
) -> AsyncIterator[str]:
    cursor = after_id
    last_output = time.monotonic()
    while not await request.is_disconnected():
        events = store.read_after(cursor)
        for stored in events:
            cursor = stored.id
            last_output = time.monotonic()
            yield _sse_frame(
                stored.id,
                stored.event.type,
                stored.event.model_dump(mode="json"),
            )
        if not events and time.monotonic() - last_output >= heartbeat_seconds:
            last_output = time.monotonic()
            yield ": keep-alive\n\n"
        await asyncio.sleep(poll_seconds)


@router.get("/events", response_class=StreamingResponse)
def events(
    request: Request,
    store: EventStoreDep,
    after_id: Annotated[int | None, Query(ge=0)] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    stream = event_stream(request, store, after_id=_cursor(after_id, last_event_id))
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
