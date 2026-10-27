from pathlib import Path


class LocalStorage:
    """Guarda los archivos bajo DATA_DIR/files."""

    def __init__(self, root: Path, url_prefix: str = "/api/v1/files") -> None:
        self.root = root.resolve()
        self.url_prefix = url_prefix.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Clave fuera del almacenamiento: {key}")
        return path

    def save_bytes(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def local_path(self, key: str) -> Path:
        return self._path(key)

    def public_url(self, key: str) -> str:
        return f"{self.url_prefix}/{key}"
