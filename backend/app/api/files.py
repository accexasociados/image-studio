from pathlib import PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.storage import Storage, get_storage

router = APIRouter(tags=["files"])
StorageDep = Annotated[Storage, Depends(get_storage)]
_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@router.get("/files/{key:path}", response_class=FileResponse)
def get_file(key: str, storage: StorageDep) -> FileResponse:
    if not storage.exists(key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado.")
    suffix = PurePosixPath(key).suffix.casefold()
    return FileResponse(storage.local_path(key), media_type=_MEDIA_TYPES.get(suffix))
