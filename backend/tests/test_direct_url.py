from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.importers.direct_url import DownloadedImage, download_image


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


def test_download_image_shortens_opaque_url_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.importers.direct_url._safe_host", lambda _: None)
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=_jpeg()))
    client = httpx.Client(transport=transport)
    token = "AP1Gcz" + "x" * 200
    result = download_image(f"https://lh3.googleusercontent.com/pw/{token}=d", client=client)
    assert result.filename == f"{token[:60]}.jpg"


def test_album_photos_are_numbered_in_album_order(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.importers import google_photos

    monkeypatch.setattr(google_photos, "fetch_album_urls", lambda _url, **_kwargs: ["u1", "u2"])
    monkeypatch.setattr(
        google_photos,
        "download_image",
        lambda url, **_kwargs: DownloadedImage(data=b"x", filename=f"{url}.jpg", media_type="image/jpeg"),
    )
    names = [image.filename for image in google_photos.download_album("https://photos.app.goo.gl/x")]
    assert names == ["google-photos-001.jpg", "google-photos-002.jpg"]
