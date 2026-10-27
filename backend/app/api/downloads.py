import re
import unicodedata
from collections.abc import Iterator
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import Annotated
from zipfile import ZIP_STORED, ZipFile

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.contracts import PRESETS, Preset
from app.db.models import BatchRow, ImageRow, OutputRow
from app.db.session import get_session
from app.db.settings_store import load_settings
from app.storage import Storage, get_storage

router = APIRouter(prefix="/batches", tags=["batches"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]

_SPOOL_LIMIT = 16 * 1024**2
_CHUNK_SIZE = 1024**2
_EXTENSIONS = {"jpeg": "jpg", "png": "png", "webp": "webp"}


def _safe_name(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-")
    return cleaned[:120] or fallback


def _selected_outputs(image: ImageRow, preset: Preset) -> list[OutputRow]:
    candidates = [output for output in image.outputs if output.preset == preset]
    if not candidates:
        return []
    latest_version = max(output.version for output in candidates)
    return sorted(
        (output for output in candidates if output.version == latest_version),
        key=lambda output: (output.variant, output.id),
    )


def _unique_name(name: str, used_names: set[str]) -> str:
    path = PurePosixPath(name)
    candidate = name
    sequence = 2
    while candidate.casefold() in used_names:
        candidate = f"{path.stem}_{sequence}{path.suffix}"
        sequence += 1
    used_names.add(candidate.casefold())
    return candidate


def _archive_name(
    image: ImageRow,
    output: OutputRow,
    output_count: int,
    extension: str,
    filename_strategy: str,
) -> str:
    original_stem = PurePosixPath(image.source_ref or image.original_path).stem
    if filename_strategy == "original":
        candidate = original_stem
    elif filename_strategy == "slug":
        candidate = image.product_name or original_stem
    else:
        candidate = image.sku or image.product_name or original_stem
    base = _safe_name(candidate, fallback=image.id)
    variant = _safe_name(output.variant, fallback="variant")
    suffix = f"_{variant}" if output.variant != "keep" else ""
    return f"{base}{suffix}.{extension}"


def _stream_file(stream: SpooledTemporaryFile[bytes]) -> Iterator[bytes]:
    try:
        while chunk := stream.read(_CHUNK_SIZE):
            yield chunk
    finally:
        stream.close()


@router.get("/{batch_id}/download/{preset}.zip", response_class=StreamingResponse)
def download_batch(
    batch_id: str,
    preset: Preset,
    session: SessionDep,
    storage: StorageDep,
    approved_only: Annotated[bool, Query(description="Incluir únicamente imágenes aprobadas.")] = True,
) -> StreamingResponse:
    """Empaqueta la versión más reciente de un preset, nombrada por SKU cuando exista."""
    batch = session.scalar(
        select(BatchRow)
        .where(BatchRow.id == batch_id)
        .options(selectinload(BatchRow.images).selectinload(ImageRow.outputs))
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")

    entries: list[tuple[ImageRow, OutputRow, int]] = []
    for image in sorted(batch.images, key=lambda item: (item.position, item.created_at, item.id)):
        if approved_only and image.status != "approved":
            continue
        outputs = _selected_outputs(image, preset)
        entries.extend((image, output, len(outputs)) for output in outputs)
    if not entries:
        scope = "aprobadas " if approved_only else ""
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lote no tiene salidas {scope}para el preset solicitado.",
        )

    # La respuesta conserva el archivo abierto y `_stream_file` lo cierra al terminar o desconectarse.
    archive = SpooledTemporaryFile(max_size=_SPOOL_LIMIT, mode="w+b")  # noqa: SIM115
    used_names: set[str] = set()
    extension = _EXTENSIONS[PRESETS[preset].format]
    filename_strategy = load_settings(session).export.filename_strategy
    try:
        with ZipFile(archive, mode="w", compression=ZIP_STORED) as zipped:
            for image, output, output_count in entries:
                name = _unique_name(
                    _archive_name(image, output, output_count, extension, filename_strategy), used_names
                )
                try:
                    content = storage.read_bytes(output.path)
                except FileNotFoundError:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Falta el archivo de salida para la imagen {image.id}.",
                    ) from None
                zipped.writestr(name, content)
        size = archive.tell()
        archive.seek(0)
    except Exception:
        archive.close()
        raise

    batch_name = _safe_name(batch.name, fallback=batch.id)
    filename = f"{batch_name}-{preset}.zip"
    return StreamingResponse(
        _stream_file(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(size),
        },
    )
