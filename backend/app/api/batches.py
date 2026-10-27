from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.contracts import Batch, BatchCounts, BatchCreate, BatchStatus, ImportRequest, ProcessOptions
from app.db.models import BatchRow, utcnow
from app.db.session import get_session
from app.queue import get_job_queue

router = APIRouter(prefix="/batches", tags=["batches"])
SessionDep = Annotated[Session, Depends(get_session)]


def _batch_response(row: BatchRow) -> Batch:
    counts = BatchCounts(total=len(row.images))
    for image in row.images:
        if image.status in {"done", "approved"}:
            counts.done += 1
        elif image.status == "review":
            counts.review += 1
        elif image.status == "failed":
            counts.failed += 1

    return Batch(
        id=row.id,
        name=row.name,
        status=cast(BatchStatus, row.status),
        default_options=ProcessOptions.model_validate(row.default_options),
        created_at=row.created_at,
        finished_at=row.finished_at,
        counts=counts,
    )


def _get_batch(session: Session, batch_id: str) -> BatchRow:
    row = session.scalar(
        select(BatchRow).where(BatchRow.id == batch_id).options(selectinload(BatchRow.images))
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")
    return row


@router.post("", response_model=Batch, status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, session: SessionDep) -> Batch:
    row = BatchRow(
        name=payload.name,
        status="draft",
        default_options=payload.default_options.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _batch_response(row)


@router.post("/{batch_id}/imports", status_code=status.HTTP_202_ACCEPTED)
def import_batch(batch_id: str, payload: ImportRequest, session: SessionDep) -> dict[str, str]:
    row = _get_batch(session, batch_id)
    if row.status not in {"draft", "failed", "queued"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El lote no admite nuevas importaciones."
        )
    job = get_job_queue().enqueue("import", batch_id=batch_id, payload={"url": payload.url}, session=session)
    row.status = "queued"
    row.finished_at = None
    session.commit()
    return {"job_id": job.id, "status": "queued"}


@router.get("", response_model=list[Batch])
def list_batches(session: SessionDep) -> list[Batch]:
    rows = session.scalars(
        select(BatchRow).options(selectinload(BatchRow.images)).order_by(BatchRow.created_at.desc())
    ).all()
    return [_batch_response(row) for row in rows]


@router.get("/{batch_id}", response_model=Batch)
def get_batch(batch_id: str, session: SessionDep) -> Batch:
    return _batch_response(_get_batch(session, batch_id))


@router.put("/{batch_id}/default-options", response_model=Batch)
def replace_default_options(batch_id: str, payload: ProcessOptions, session: SessionDep) -> Batch:
    row = _get_batch(session, batch_id)
    row.default_options = payload.model_dump(mode="json")
    session.commit()
    session.refresh(row)
    return _batch_response(row)


@router.post("/{batch_id}/cancel", response_model=Batch)
def cancel_batch(batch_id: str, session: SessionDep) -> Batch:
    row = _get_batch(session, batch_id)
    if row.status == "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un lote terminado no se puede cancelar.",
        )
    if row.status != "cancelled":
        now = utcnow()
        row.status = "cancelled"
        row.finished_at = now
        get_job_queue().cancel_batch(batch_id, session=session)
        session.commit()
        session.refresh(row)
    return _batch_response(row)


@router.post("/{batch_id}/retry-failed", response_model=Batch)
def retry_failed_images(batch_id: str, session: SessionDep) -> Batch:
    row = _get_batch(session, batch_id)
    failed_images = [image for image in row.images if image.status == "failed"]
    if not failed_images:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El lote no tiene imágenes fallidas para reintentar.",
        )

    for image in failed_images:
        image.status = "pending"
        image.error = None
        image.review_reasons = []
        get_job_queue().enqueue("process", image_id=image.id, batch_id=row.id, session=session)

    row.status = "queued"
    row.finished_at = None
    session.commit()
    session.refresh(row)
    return _batch_response(row)
