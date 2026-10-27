import httpx
import pytest

from app.importers import google_drive
from app.importers.direct_url import DownloadedImage
from app.importers.google_drive import download_drive, extract_drive_id


def test_extract_drive_ids_from_file_folder_and_query_links() -> None:
    assert extract_drive_id("https://drive.google.com/file/d/abc-123/view") == "abc-123"
    assert extract_drive_id("https://drive.google.com/open?id=folder_1") == "folder_1"
    assert extract_drive_id("https://drive.google.com/drive/folders/fold-9?usp=sharing") == "fold-9"
    assert extract_drive_id("https://drive.google.com/drive/u/0/folders/fold-9") == "fold-9"


def test_public_file_without_api_key_skips_the_drive_api(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def fake_download(url: str, **_kwargs: object) -> DownloadedImage:
        requested.append(url)
        return DownloadedImage(data=b"x", filename="a.jpg", media_type="image/jpeg")

    monkeypatch.setattr(google_drive, "download_image", fake_download)
    # Sin clave la API de Drive responde 403; no debe consultarse.
    api = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(403)))

    images = list(download_drive("https://drive.google.com/file/d/abc-123/view", client=api))

    assert len(images) == 1
    assert requested == ["https://drive.usercontent.google.com/download?id=abc-123&export=download"]


def test_folder_without_api_key_explains_what_is_missing() -> None:
    with pytest.raises(ValueError, match="clave de API"):
        list(download_drive("https://drive.google.com/drive/folders/fold-9"))
