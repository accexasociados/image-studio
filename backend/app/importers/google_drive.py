"""Importador de archivos y carpetas públicas de Google Drive."""

import re
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import httpx

from app.importers.direct_url import DownloadedImage, download_image

_FILE_ID = re.compile(r"/file/d/([\w-]+)")


def extract_drive_id(url: str) -> str:
    parsed = urlparse(url)
    match = _FILE_ID.search(parsed.path)
    if match:
        return match.group(1)
    value = parse_qs(parsed.query).get("id", [None])[0]
    if value:
        return value
    raise ValueError("No se encontró un ID de Drive en el enlace.")


def download_drive(
    url: str, *, api_key: str | None = None, client: httpx.Client | None = None
) -> Iterator[DownloadedImage]:
    """Descarga un archivo o las imágenes de una carpeta pública."""
    owns_client = client is None
    session = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        resource_id = extract_drive_id(url)
        params = {"key": api_key} if api_key else {}
        metadata = session.get(
            f"https://www.googleapis.com/drive/v3/files/{resource_id}",
            params={**params, "fields": "id,name,mimeType"},
        )
        if metadata.status_code == 404 and not api_key:
            yield download_image(
                f"https://drive.usercontent.google.com/download?id={resource_id}&export=download",
                client=session,
            )
            return
        metadata.raise_for_status()
        item = metadata.json()
        if item.get("mimeType") == "application/vnd.google-apps.folder":
            listing = session.get(
                "https://www.googleapis.com/drive/v3/files",
                params={
                    **params,
                    "q": f"'{resource_id}' in parents and trashed = false",
                    "fields": "files(id,name,mimeType)",
                },
            )
            listing.raise_for_status()
            for child in listing.json().get("files", []):
                if child.get("mimeType", "").startswith("image/"):
                    yield download_image(
                        f"https://drive.usercontent.google.com/download?id={child['id']}&export=download",
                        client=session,
                    )
            return
        if not item.get("mimeType", "").startswith("image/"):
            raise ValueError("El archivo de Drive no es una imagen.")
        yield download_image(
            f"https://drive.usercontent.google.com/download?id={resource_id}&export=download", client=session
        )
    finally:
        if owns_client:
            session.close()
