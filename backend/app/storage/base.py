"""Almacenamiento de archivos (originales, máscaras, salidas). Las rutas guardadas en la BD son
claves relativas ("batches/<id>/originals/foto.jpg"), así el mismo registro sirve en local y en S3."""

from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def save_bytes(self, key: str, data: bytes) -> str: ...

    def read_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None: ...

    def local_path(self, key: str) -> Path:
        """Ruta en disco para el proceso de imagen. En S3 descarga a una caché local."""
        ...

    def public_url(self, key: str) -> str:
        """URL para mostrar el archivo en la web (ruta de la API en local, URL firmada en S3)."""
        ...
