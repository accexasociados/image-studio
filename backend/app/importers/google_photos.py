"""Lector aislado del HTML de álbumes compartidos de Google Photos."""

import re
from collections.abc import Iterable
from dataclasses import replace

import httpx

from app.importers.direct_url import MAX_IMAGE_BYTES, DownloadedImage, _validate_url, download_image

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
        timeout=20.0, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        current = url
        for _ in range(6):
            _validate_url(current)
            response = session.get(current, headers={"User-Agent": "Mozilla/5.0"})
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("La redirección no tiene destino.")
                current = str(httpx.URL(current).join(location))
                continue
            break
        else:
            raise ValueError("Demasiadas redirecciones.")
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


def download_album(
    url: str, *, max_bytes: int = MAX_IMAGE_BYTES, client: httpx.Client | None = None
) -> Iterable[DownloadedImage]:
    """Descarga las imágenes del álbum; la paginación queda aislada aquí."""
    for index, photo_url in enumerate(fetch_album_urls(url, client=client), start=1):
        image = download_image(photo_url, max_bytes=max_bytes, client=client)
        extension = image.filename.rsplit(".", 1)[-1]
        # El nombre de la URL es un token opaco: se numera en el orden del álbum.
        yield replace(image, filename=f"google-photos-{index:03d}.{extension}")
