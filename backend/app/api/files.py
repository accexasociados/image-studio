from io import BytesIO
from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

from app.storage import Storage, get_storage

router = APIRouter(tags=["files"])
StorageDep = Annotated[Storage, Depends(get_storage)]
_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
# Anchos fijos para que la caché de miniaturas no crezca con cada valor que pida un cliente.
_THUMB_WIDTHS = (320, 640, 1280)
_THUMBS_PREFIX = "thumbs"


def _thumbnail(storage: Storage, key: str, width: int) -> str:
    """Miniatura WebP con EXIF aplicado. Las claves de originales, salidas y máscaras no se
    reescriben (llevan versión o UUID), así que la miniatura cacheada nunca queda vieja."""
    thumb_key = f"{_THUMBS_PREFIX}/w{width}/{key}.webp"
    if storage.exists(thumb_key):
        return thumb_key
    with Image.open(storage.local_path(key)) as opened:
        image = ImageOps.exif_transpose(opened)
        image = image.convert("L" if image.mode in {"L", "I", "I;16", "1"} else "RGB")
        if image.width > width:
            height = max(1, round(image.height * width / image.width))
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="WEBP", quality=82)
    storage.save_bytes(thumb_key, buffer.getvalue())
    return thumb_key


@router.get("/files/{key:path}", response_class=FileResponse)
def get_file(
    key: str,
    storage: StorageDep,
    w: Annotated[int | None, Query(description="Ancho de la miniatura WebP: 320, 640 o 1280.")] = None,
) -> FileResponse:
    if w is not None and w not in _THUMB_WIDTHS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Ancho de miniatura no admitido. Usa {', '.join(map(str, _THUMB_WIDTHS))}.",
        )
    try:
        exists = storage.exists(key)
    except ValueError:
        exists = False
    if not exists or key.startswith(f"{_THUMBS_PREFIX}/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado.")
    if w is not None:
        return FileResponse(
            storage.local_path(_thumbnail(storage, key, w)),
            media_type="image/webp",
            headers={"Cache-Control": "private, max-age=31536000, immutable"},
        )
    suffix = PurePosixPath(key).suffix.casefold()
    return FileResponse(storage.local_path(key), media_type=_MEDIA_TYPES.get(suffix))
