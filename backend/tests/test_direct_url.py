from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.importers.direct_url import download_image


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="JPEG")
    return output.getvalue()


def test_download_image_follows_redirect_and_validates_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.importers.direct_url._safe_host", lambda _: None)
    responses = [
        httpx.Response(302, headers={"location": "https://example.com/photo.jpg"}),
        httpx.Response(200, content=_jpeg()),
    ]
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: responses.pop(0)), follow_redirects=False
    )
    result = download_image("https://example.com/album", client=client)
    assert result.filename == "photo.jpg"
    assert result.media_type == "image/jpeg"


def test_download_image_rejects_private_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.importers.direct_url.socket.getaddrinfo", lambda *_: [(None, None, None, None, ("127.0.0.1", 0))]
    )
    with pytest.raises(ValueError, match="privada"):
        download_image("http://localhost/photo.jpg")
