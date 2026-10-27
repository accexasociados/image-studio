from app.importers.google_drive import extract_drive_id


def test_extract_drive_ids_from_file_and_query_links() -> None:
    assert extract_drive_id("https://drive.google.com/file/d/abc-123/view") == "abc-123"
    assert extract_drive_id("https://drive.google.com/open?id=folder_1") == "folder_1"
