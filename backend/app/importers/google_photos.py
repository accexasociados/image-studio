"""Lector aislado del HTML de álbumes compartidos de Google Photos."""

import re
from collections.abc import Iterable

import httpx

from app.importers.direct_url import DownloadedImage, download_image

_PHOTO_URL = re.compile(r"https://lh3\.googleusercontent\.com/[A-Za-z0-9_/?=&%-]+")


def extract_photo_urls(html: str) -> list[str]:
    """Extrae fotos reales del álbum y normaliza el sufijo de resolución original."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in _PHOTO_URL.findall(html):
        url = raw.split('"', 1)[0]
        if "/pw/" not in url or "w600-h315-p-k" in url:
            continue
        original = f"{url.split('=', 1)[0]}=d"
        if original not in seen:
            seen.add(original)
            result.append(original)
    return result


def fetch_album_urls(url: str, *, client: httpx.Client | None = None) -> list[str]:
    owns_client = client is None
    session = client or httpx.Client(
        timeout=20.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        response = session.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        urls = extract_photo_urls(response.text)
        if not urls:
            raise ValueError(
                "Google Photos no expuso las fotos del álbum; vuelve a intentarlo o usa enlaces directos."
            )
        return urls
    finally:
        if owns_client:
            session.close()


def download_album(url: str, *, client: httpx.Client | None = None) -> Iterable[DownloadedImage]:
    """Descarga las imágenes del álbum; la paginación queda aislada aquí."""
    for photo_url in fetch_album_urls(url, client=client):
        yield download_image(photo_url, client=client)
