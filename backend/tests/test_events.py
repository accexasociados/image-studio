import asyncio
import json
from collections.abc import Iterator

import pytest
from fastapi import HTTPException

from app.api.events import _cursor, event_stream
from app.contracts import Event
from app.db.migrate import upgrade_to_head
from app.events import get_event_store


@pytest.fixture(autouse=True)
def migrated_database() -> Iterator[None]:
    upgrade_to_head()
    yield


class _ConnectedRequest:
    def __init__(self) -> None:
        self.checks = 0

    async def is_disconnected(self) -> bool:
        self.checks += 1
        return self.checks > 1


def test_event_store_is_ordered_and_supports_resume_cursor() -> None:
    store = get_event_store()
    first_id = store.publish(Event(type="image.updated", payload={"image_id": "one"}))
    second_id = store.publish(Event(type="batch.progress", payload={"batch_id": "batch"}))

    all_events = store.read_after(0)
    resumed = store.read_after(first_id)

    assert [event.id for event in all_events] == [first_id, second_id]
    assert [event.id for event in resumed] == [second_id]
    assert resumed[0].event.type == "batch.progress"


def test_event_stream_formats_a_resumable_sse_frame() -> None:
    store = get_event_store()
    event_id = store.publish(Event(type="batch.finished", payload={"batch_id": "batch"}))

    async def first_frame() -> str:
        stream = event_stream(_ConnectedRequest(), store, after_id=0, poll_seconds=0)
        return await anext(stream)

    frame = asyncio.run(first_frame())
    lines = frame.strip().splitlines()
    assert lines[0] == f"id: {event_id}"
    assert lines[1] == "event: batch.finished"
    assert json.loads(lines[2].removeprefix("data: ")) == {
        "type": "batch.finished",
        "payload": {"batch_id": "batch"},
    }


def test_cursor_prefers_query_and_validates_header() -> None:
    assert _cursor(7, "2") == 7
    assert _cursor(None, "2") == 2
    assert _cursor(None, None) == 0
    with pytest.raises(HTTPException):
        _cursor(None, "invalid")
