"""Biblioteca de fotos de fondo para la escena "photo" (Fase 11)."""

from io import BytesIO
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.images import _read_limited, _validated_image
from app.contracts import SceneBackground, SceneBackgroundUpdate
from app.db.models import BackgroundRow
from app.db.session import get_session
from app.db.settings_store import load_settings, save_settings
from app.storage import Storage, get_storage

router = APIRouter(prefix="/backgrounds", tags=["backgrounds"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def _response(row: BackgroundRow, storage: Storage) -> SceneBackground:
    return SceneBackground(
        id=row.id,
        name=row.name,
        url=storage.public_url(row.path),
        width=row.width,
        height=row.height,
        floor_y=row.floor_y,
        center_x=row.center_x,
        piece_height=row.piece_height,
        created_at=row.created_at,
    )


def _get(session: Session, background_id: str) -> BackgroundRow:
    row = session.get(BackgroundRow, background_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fondo no encontrado.")
    return row


@router.get("", response_model=list[SceneBackground])
def list_backgrounds(session: SessionDep, storage: StorageDep) -> list[SceneBackground]:
    rows = session.scalars(select(BackgroundRow).order_by(BackgroundRow.created_at)).all()
    return [_response(row, storage) for row in rows]


@router.post("", response_model=SceneBackground, status_code=status.HTTP_201_CREATED)
def upload_background(
    file: Annotated[UploadFile, File(description="Foto de fondo JPEG, PNG o WebP")],
    session: SessionDep,
    storage: StorageDep,
    name: Annotated[str | None, Form(max_length=120)] = None,
) -> SceneBackground:
    settings = load_settings(session)
    source_name = file.filename or "fondo"
    data, extension = _validated_image(
        _read_limited(file.file, settings.importers.max_download_mb * 1024**2), source_name
    )
    with Image.open(BytesIO(data)) as opened:
        width, height = ImageOps.exif_transpose(opened).size
    row = BackgroundRow(
        name=(name or PurePosixPath(source_name).stem or "Fondo")[:120],
        path="pending",
        width=width,
        height=height,
    )
    session.add(row)
    session.flush()
    row.path = f"backgrounds/{row.id}.{extension}"
    storage.save_bytes(row.path, data)
    # El primer fondo queda como predeterminado para que la escena "photo" funcione sin más pasos.
    if settings.export.scene.default_background_id is None:
        settings.export.scene.default_background_id = row.id
        save_settings(session, settings)
    session.commit()
    return _response(row, storage)


@router.patch("/{background_id}", response_model=SceneBackground)
def update_background(
    background_id: str, payload: SceneBackgroundUpdate, session: SessionDep, storage: StorageDep
) -> SceneBackground:
    row = _get(session, background_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(row, key, value)
    session.commit()
    return _response(row, storage)


@router.delete("/{background_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_background(background_id: str, session: SessionDep, storage: StorageDep) -> None:
    row = _get(session, background_id)
    settings = load_settings(session)
    if settings.export.scene.default_background_id == row.id:
        settings.export.scene.default_background_id = None
        save_settings(session, settings)
    path = row.path
    session.delete(row)
    session.commit()
    storage.delete(path)
