from functools import lru_cache

from app.config import get_settings
from app.storage.base import Storage
from app.storage.local import LocalStorage


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        raise NotImplementedError("Almacenamiento S3 pendiente (Fase 9).")
    return LocalStorage(settings.data_dir / "files")


__all__ = ["LocalStorage", "Storage", "get_storage"]
