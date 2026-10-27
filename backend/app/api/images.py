import csv
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from typing import IO, Annotated, cast
from warnings import catch_warnings, simplefilter
from zipfile import BadZipFile, ZipFile, ZipInfo, is_zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.contracts import ImageItem, ImageSource, ImageStatus, ImageUpdate, OutputFile, ProcessOptions
from app.db.models import BatchRow, ImageRow, JobRow
from app.db.session import get_session
from app.db.settings_store import load_settings
from app.storage import Storage, get_storage

router = APIRouter(tags=["images"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]

_MAX_IMAGES_PER_UPLOAD = 200
_MAX_ARCHIVE_BYTES = 2 * 1024**3
_MAX_CSV_BYTES = 2 * 1024**2
_MAX_CSV_ROWS = 2000
_IMAGE_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


@dataclass(frozen=True)
class _MetadataRow:
    line: int
    filename: str
    product_name: str | None
    sku: str | None


def _image_response(row: ImageRow) -> ImageItem:
    return ImageItem(
        id=row.id,
        batch_id=row.batch_id,
        source=cast(ImageSource, row.source),
        source_ref=row.source_ref,
        original_path=row.original_path,
        product_name=row.product_name,
        sku=row.sku,
        options_override=(
            ProcessOptions.model_validate(row.options_override) if row.options_override is not None else None
        ),
        status=cast(ImageStatus, row.status),
        review_reasons=row.review_reasons,
        outputs=[OutputFile.model_validate(output) for output in row.outputs],
        error=row.error,
        mask_path=row.mask_path,
    )


def _get_image(session: Session, image_id: str) -> ImageRow:
    row = session.scalar(
        select(ImageRow).where(ImageRow.id == image_id).options(selectinload(ImageRow.outputs))
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagen no encontrada.")
    return row


def _read_limited(stream: IO[bytes], max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    remaining = max_bytes + 1
    while remaining > 0:
        chunk = stream.read(min(1024 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Una imagen supera el límite de {max_bytes // 1024**2} MB.",
        )
    return data


def _validated_image(data: bytes, source_name: str) -> tuple[bytes, str]:
    try:
        with catch_warnings():
            simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image.verify()
                image_format = image.format
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{source_name}' no es una imagen válida o segura.",
        ) from None

    extension = _IMAGE_EXTENSIONS.get(image_format or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"'{source_name}' usa un formato no admitido. Usa JPEG, PNG o WebP.",
        )
    return data, extension


def _is_ignored_zip_entry(info: ZipInfo) -> bool:
    path = PurePosixPath(info.filename)
    return info.is_dir() or "__MACOSX" in path.parts or path.name in {".DS_Store", "Thumbs.db"}


def _zip_images(upload: UploadFile, max_image_bytes: int) -> Iterator[tuple[str, bytes, str]]:
    try:
        with ZipFile(upload.file) as archive:
            infos = [info for info in archive.infolist() if not _is_ignored_zip_entry(info)]
            if not infos:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El ZIP no contiene imágenes.",
                )
            if any(info.flag_bits & 0x1 for info in infos):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No se admiten archivos ZIP cifrados.",
                )
            if any(info.file_size > max_image_bytes for info in infos):
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Una imagen del ZIP supera el límite de {max_image_bytes // 1024**2} MB.",
                )
            if sum(info.file_size for info in infos) > _MAX_ARCHIVE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="El contenido descomprimido del ZIP supera 2 GB.",
                )

            for info in infos:
                source_name = PurePosixPath(info.filename).name
                with archive.open(info) as member:
                    data = _read_limited(member, max_image_bytes)
                validated, extension = _validated_image(data, source_name)
                yield source_name, validated, extension
    except BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo ZIP está dañado.",
        ) from None


def _upload_images(upload: UploadFile, max_image_bytes: int) -> Iterator[tuple[str, bytes, str]]:
    source_name = PurePosixPath(upload.filename or "imagen").name
    upload.file.seek(0)
    header = upload.file.read(4)
    upload.file.seek(0)
    if header.startswith(b"PK"):
        if not is_zipfile(upload.file):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo ZIP está dañado.")
        upload.file.seek(0)
        yield from _zip_images(upload, max_image_bytes)
        return

    data = _read_limited(upload.file, max_image_bytes)
    validated, extension = _validated_image(data, source_name)
    yield source_name, validated, extension


def _metadata_rows(upload: UploadFile) -> list[_MetadataRow]:
    data = upload.file.read(_MAX_CSV_BYTES + 1)
    if len(data) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="El CSV supera el límite de 2 MB.",
        )
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El CSV debe estar codificado en UTF-8.",
        ) from None

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    parsed = list(csv.reader(StringIO(text), dialect=dialect))
    if not parsed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El CSV está vacío.")

    headers = [header.strip().casefold() for header in parsed[0]]
    required = ("archivo", "nombre", "sku")
    if any(headers.count(header) != 1 for header in required):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El CSV debe contener una sola columna de archivo, nombre y sku.",
        )
    indexes = {header: headers.index(header) for header in required}
    result: list[_MetadataRow] = []
    for line, values in enumerate(parsed[1:], start=2):
        if not any(value.strip() for value in values):
            continue
        if len(result) >= _MAX_CSV_ROWS:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"El CSV supera el límite de {_MAX_CSV_ROWS} filas.",
            )
        filename = values[indexes["archivo"]].strip() if indexes["archivo"] < len(values) else ""
        product_name = values[indexes["nombre"]].strip() if indexes["nombre"] < len(values) else ""
        sku = values[indexes["sku"]].strip() if indexes["sku"] < len(values) else ""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"La fila {line} no tiene archivo.",
            )
        result.append(
            _MetadataRow(
                line=line,
                filename=filename,
                product_name=product_name or None,
                sku=sku or None,
            )
        )
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El CSV no contiene datos.")
    return result


def _filename_key(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/")).name.casefold()


@router.post(
    "/batches/{batch_id}/images",
    response_model=list[ImageItem],
    status_code=status.HTTP_201_CREATED,
)
def upload_images(
    batch_id: str,
    files: Annotated[list[UploadFile], File(description="Imágenes o archivos ZIP")],
    session: SessionDep,
    storage: StorageDep,
) -> list[ImageItem]:
    batch = session.get(BatchRow, batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")
    if batch.status not in {"draft", "queued", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden agregar imágenes a un lote editable.",
        )
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes enviar al menos un archivo.",
        )

    max_image_bytes = load_settings(session).importers.max_download_mb * 1024**2
    saved_keys: list[str] = []
    created: list[ImageRow] = []
    try:
        for upload in files:
            for source_name, data, extension in _upload_images(upload, max_image_bytes):
                if len(created) >= _MAX_IMAGES_PER_UPLOAD:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Solo se admiten {_MAX_IMAGES_PER_UPLOAD} imágenes por subida.",
                    )
                row = ImageRow(
                    batch_id=batch.id,
                    source="upload",
                    source_ref=source_name,
                    original_path="pending",
                    status="pending",
                    position=len(batch.images) + len(created),
                )
                session.add(row)
                session.flush()
                key = f"batches/{batch.id}/originals/{row.id}.{extension}"
                storage.save_bytes(key, data)
                saved_keys.append(key)
                row.original_path = key
                session.add(JobRow(kind="process", status="queued", image_id=row.id, batch_id=batch.id))
                created.append(row)

        if not created:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se recibieron imágenes.")
        batch.status = "queued"
        batch.finished_at = None
        session.commit()
    except Exception:
        session.rollback()
        for key in saved_keys:
            storage.delete(key)
        raise

    return [_image_response(row) for row in created]


@router.get("/batches/{batch_id}/images", response_model=list[ImageItem])
def list_batch_images(batch_id: str, session: SessionDep) -> list[ImageItem]:
    if session.get(BatchRow, batch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")
    rows = session.scalars(
        select(ImageRow)
        .where(ImageRow.batch_id == batch_id)
        .options(selectinload(ImageRow.outputs))
        .order_by(ImageRow.position, ImageRow.created_at)
    ).all()
    return [_image_response(row) for row in rows]


@router.post("/batches/{batch_id}/metadata-csv", response_model=list[ImageItem])
def import_metadata_csv(
    batch_id: str,
    file: Annotated[UploadFile, File(description="CSV con columnas archivo,nombre,sku")],
    session: SessionDep,
) -> list[ImageItem]:
    if session.get(BatchRow, batch_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote no encontrado.")

    images = session.scalars(
        select(ImageRow)
        .where(ImageRow.batch_id == batch_id)
        .options(selectinload(ImageRow.outputs))
        .order_by(ImageRow.position, ImageRow.created_at)
    ).all()
    by_filename: dict[str, list[ImageRow]] = {}
    for image in images:
        source_name = image.source_ref or image.original_path
        by_filename.setdefault(_filename_key(source_name), []).append(image)

    assignments: list[tuple[ImageRow, ImageUpdate]] = []
    seen: set[str] = set()
    for metadata in _metadata_rows(file):
        key = _filename_key(metadata.filename)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"El archivo '{metadata.filename}' aparece más de una vez en el CSV.",
            )
        seen.add(key)
        matches = by_filename.get(key, [])
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"La fila {metadata.line} referencia un archivo que no pertenece al lote.",
            )
        if len(matches) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El nombre '{metadata.filename}' es ambiguo dentro del lote.",
            )
        try:
            update_payload = ImageUpdate(product_name=metadata.product_name, sku=metadata.sku)
        except ValidationError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"La fila {metadata.line} contiene un nombre o SKU inválido.",
            ) from None
        assignments.append((matches[0], update_payload))

    for image, payload in assignments:
        image.product_name = payload.product_name
        image.sku = payload.sku
    session.commit()
    for image, _payload in assignments:
        session.refresh(image)
    return [_image_response(image) for image, _payload in assignments]


@router.get("/images/{image_id}", response_model=ImageItem)
def get_image(image_id: str, session: SessionDep) -> ImageItem:
    return _image_response(_get_image(session, image_id))


@router.patch("/images/{image_id}", response_model=ImageItem)
def update_image(image_id: str, payload: ImageUpdate, session: SessionDep) -> ImageItem:
    row = _get_image(session, image_id)
    fields = payload.model_fields_set
    if "product_name" in fields:
        row.product_name = payload.product_name
    if "sku" in fields:
        row.sku = payload.sku
    if "options_override" in fields:
        row.options_override = (
            payload.options_override.model_dump(mode="json") if payload.options_override is not None else None
        )
    session.commit()
    session.refresh(row)
    return _image_response(row)


@router.post("/images/{image_id}/approve", response_model=ImageItem)
def approve_image(image_id: str, session: SessionDep) -> ImageItem:
    row = _get_image(session, image_id)
    if row.status not in {"done", "review", "approved"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La imagen debe estar procesada antes de aprobarla.",
        )
    if row.status != "approved":
        row.status = "approved"
        session.commit()
        session.refresh(row)
    return _image_response(row)
