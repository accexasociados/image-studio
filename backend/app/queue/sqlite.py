from datetime import timedelta
from typing import Any, cast

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.contracts import Job, JobKind, JobStatus
from app.db.models import JobRow, utcnow

_MAX_ATTEMPTS = 3
_STALE_AFTER = timedelta(minutes=5)


class SQLiteJobQueue:
    """Cola persistente; `BEGIN IMMEDIATE` serializa la toma de trabajos entre workers."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def enqueue(
        self,
        kind: JobKind,
        *,
        image_id: str | None = None,
        batch_id: str | None = None,
        payload: dict[str, Any] | None = None,
        session: Session | None = None,
    ) -> Job:
        if image_id is None and batch_id is None:
            raise ValueError("Un trabajo debe pertenecer a una imagen o a un lote.")
        own_session = session is None
        active_session = session or self._session_factory()
        try:
            row = JobRow(
                kind=kind,
                status="queued",
                image_id=image_id,
                batch_id=batch_id,
                payload=dict(payload or {}),
            )
            active_session.add(row)
            if own_session:
                active_session.commit()
            else:
                active_session.flush()
            active_session.refresh(row)
            return _job_response(row)
        finally:
            if own_session:
                active_session.close()

    def claim_next(self, worker_id: str) -> Job | None:
        if not worker_id.strip():
            raise ValueError("worker_id no puede estar vacío.")
        with self._session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            row = session.scalar(
                select(JobRow)
                .where(JobRow.status == "queued")
                .order_by(JobRow.created_at, JobRow.id)
                .limit(1)
            )
            if row is None:
                session.commit()
                return None

            row.status = "running"
            row.attempts += 1
            row.started_at = utcnow()
            row.finished_at = None
            row.payload = {**row.payload, "worker_id": worker_id}
            session.commit()
            session.refresh(row)
            return _job_response(row)

    def complete(self, job_id: str) -> None:
        with self._session_factory() as session:
            row = _get_job(session, job_id)
            if row.status != "running":
                raise ValueError("Solo se puede completar un trabajo en ejecución.")
            row.status = "done"
            row.error = None
            row.finished_at = utcnow()
            session.commit()

    def fail(self, job_id: str, error: str, *, retry: bool) -> None:
        with self._session_factory() as session:
            row = _get_job(session, job_id)
            if row.status != "running":
                raise ValueError("Solo puede fallar un trabajo en ejecución.")
            row.error = error
            if retry and row.attempts < _MAX_ATTEMPTS:
                row.status = "queued"
                row.started_at = None
                row.finished_at = None
                row.payload = {key: value for key, value in row.payload.items() if key != "worker_id"}
            else:
                row.status = "failed"
                row.finished_at = utcnow()
            session.commit()

    def cancel_batch(self, batch_id: str, *, session: Session | None = None) -> int:
        now = utcnow()
        own_session = session is None
        active_session = session or self._session_factory()
        try:
            rows = active_session.scalars(
                select(JobRow).where(JobRow.batch_id == batch_id, JobRow.status.in_(("queued", "running")))
            ).all()
            for row in rows:
                row.status = "cancelled"
                row.finished_at = now
            if own_session:
                active_session.commit()
            return len(rows)
        finally:
            if own_session:
                active_session.close()

    def cancel_job(self, job_id: str) -> None:
        with self._session_factory() as session:
            row = _get_job(session, job_id)
            if row.status in {"queued", "running"}:
                row.status = "cancelled"
                row.finished_at = utcnow()
                session.commit()

    def recover_stale(self) -> int:
        with self._session_factory() as session:
            cutoff = utcnow() - _STALE_AFTER
            rows = session.scalars(
                select(JobRow).where(JobRow.status == "running", JobRow.started_at < cutoff)
            ).all()
            for row in rows:
                if row.attempts >= _MAX_ATTEMPTS:
                    row.status = "failed"
                    row.finished_at = utcnow()
                else:
                    row.attempts += 1
                    row.status = "queued"
                    row.started_at = None
                    row.finished_at = None
                    row.payload = {key: value for key, value in row.payload.items() if key != "worker_id"}
            session.commit()
            return len(rows)


def _get_job(session: Session, job_id: str) -> JobRow:
    row = session.get(JobRow, job_id)
    if row is None:
        raise KeyError(f"Trabajo no encontrado: {job_id}")
    return row


def _job_response(row: JobRow) -> Job:
    return Job(
        id=row.id,
        image_id=row.image_id,
        batch_id=row.batch_id,
        kind=cast(JobKind, row.kind),
        status=cast(JobStatus, row.status),
        attempts=row.attempts,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
