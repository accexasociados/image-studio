from dataclasses import dataclass
from typing import Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts import Event, EventType
from app.db.models import EventRow
from app.db.session import get_sessionmaker


@dataclass(frozen=True)
class StoredEvent:
    id: int
    event: Event


class EventPublisher(Protocol):
    def publish(self, event: Event) -> int: ...


class SQLiteEventStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def publish(self, event: Event) -> int:
        with self._session_factory() as session:
            row = EventRow(type=event.type, payload=event.payload)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id

    def read_after(self, event_id: int, *, limit: int = 100) -> list[StoredEvent]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(EventRow).where(EventRow.id > event_id).order_by(EventRow.id).limit(limit)
            ).all()
            return [
                StoredEvent(
                    id=row.id,
                    event=Event(type=cast(EventType, row.type), payload=row.payload),
                )
                for row in rows
            ]


def get_event_store() -> SQLiteEventStore:
    return SQLiteEventStore(get_sessionmaker())


__all__ = ["EventPublisher", "SQLiteEventStore", "StoredEvent", "get_event_store"]
