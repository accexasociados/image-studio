import httpx
import pytest

from app.importers.google_photos import extract_photo_urls, fetch_album_urls


def test_extract_photo_urls_deduplicates_and_requests_original() -> None:
    html = '"https://lh3.googleusercontent.com/pw/album", "https://lh3.googleusercontent.com/pw/photo1=w800" "https://lh3.googleusercontent.com/pw/photo1=w800"'
    assert extract_photo_urls(html) == [
        "https://lh3.googleusercontent.com/pw/album=d",
        "https://lh3.googleusercontent.com/pw/photo1=d",
    ]


def test_extract_photo_urls_ignores_cover_and_avatars_and_replaces_size() -> None:
    html = (
        '"https://lh3.googleusercontent.com/pw/photo1=w600-h315-p-k=d" '
        '"https://lh3.googleusercontent.com/a/avatar=s96-c" '
        '"https://lh3.googleusercontent.com/ogw/avatar=s96-c" '
        '"https://lh3.googleusercontent.com/pw/photo2=w1200-h900"'
    )
    assert extract_photo_urls(html) == [
        "https://lh3.googleusercontent.com/pw/photo2=d",
    ]


def test_fetch_album_uses_browser_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, text="https://lh3.googleusercontent.com/pw/photo=w100")

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    assert fetch_album_urls("https://photos.google.com/share/test", client=client)
    assert seen and "Mozilla" in seen[0]


def test_fetch_album_reports_when_page_only_contains_cover() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, text='"https://lh3.googleusercontent.com/pw/cover=w600-h315-p-k"'
            )
        )
    )
    try:
        with pytest.raises(ValueError, match="no expuso"):
            fetch_album_urls("https://photos.google.com/share/test", client=client)
    finally:
        client.close()
