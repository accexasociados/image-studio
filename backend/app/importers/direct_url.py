"""Descarga segura de una imagen desde una URL directa."""

import ipaddress
import socket
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urljoin, urlparse

import httpx
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_REDIRECTS = 5


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    filename: str
    media_type: str


def _safe_host(hostname: str) -> None:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except socket.gaierror as error:
        raise ValueError("No se pudo resolver el host.") from error
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_reserved
            or parsed.is_multicast
        ):
            raise ValueError("La URL apunta a una red privada o reservada.")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("La URL debe usar http o https.")
    _safe_host(parsed.hostname)


def download_image(
    url: str, *, max_bytes: int = MAX_IMAGE_BYTES, client: httpx.Client | None = None
) -> DownloadedImage:
    """Descarga una imagen siguiendo redirecciones solo hacia hosts públicos."""
    current = url
    owns_client = client is None
    session = client or httpx.Client(timeout=20.0, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_url(current)
            response = session.get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("La redirección no tiene destino.")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            if int(response.headers.get("content-length", "0")) > max_bytes:
                raise ValueError("La imagen supera el límite permitido.")
            data = response.content
            if len(data) > max_bytes:
                raise ValueError("La imagen supera el límite permitido.")
            try:
                with Image.open(BytesIO(data)) as image:
                    image.verify()
                    image_format = image.format or ""
            except (UnidentifiedImageError, OSError) as error:
                raise ValueError("La respuesta no es una imagen válida.") from error
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}.get(image_format)
            if extension is None:
                raise ValueError("Solo se admiten JPEG, PNG y WebP.")
            name = (urlparse(current).path.rsplit("/", 1)[-1] or f"imagen.{extension}").split("?")[0]
            if "." not in name:
                name = f"{name}.{extension}"
            return DownloadedImage(
                data=data, filename=name, media_type=f"image/{'jpeg' if extension == 'jpg' else extension}"
            )
        raise ValueError("Demasiadas redirecciones.")
    finally:
        if owns_client:
            session.close()
