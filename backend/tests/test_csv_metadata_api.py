from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app


def _image_bytes(color: str) -> bytes:
    stream = BytesIO()
    Image.new("RGB", (10, 10), color).save(stream, format="PNG")
    return stream.getvalue()


def _batch_with_images(client: TestClient, *, duplicate_names: bool = False) -> tuple[str, list[str]]:
    batch_id = client.post("/api/v1/batches", json={"name": "CSV"}).json()["id"]
    second_name = "uno.png" if duplicate_names else "dos.png"
    uploaded = client.post(
        f"/api/v1/batches/{batch_id}/images",
        files=[
            ("files", ("uno.png", _image_bytes("red"), "image/png")),
            ("files", (second_name, _image_bytes("blue"), "image/png")),
        ],
    ).json()
    return batch_id, [image["id"] for image in uploaded]


def test_import_csv_updates_images_by_filename_with_excel_format() -> None:
    csv_data = "\ufeffarchivo;nombre;sku\r\nUNO.PNG;Dragón rojo;DRG-01\r\ndos.png;;AZUL_2\r\n".encode()
    with TestClient(create_app()) as client:
        batch_id, image_ids = _batch_with_images(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/metadata-csv",
            files={"file": ("productos.csv", csv_data, "text/csv")},
        )
        first = client.get(f"/api/v1/images/{image_ids[0]}").json()
        second = client.get(f"/api/v1/images/{image_ids[1]}").json()

    assert response.status_code == 200
    assert [image["id"] for image in response.json()] == image_ids
    assert first["product_name"] == "Dragón rojo"
    assert first["sku"] == "DRG-01"
    assert second["product_name"] is None
    assert second["sku"] == "AZUL_2"


def test_invalid_csv_row_does_not_apply_previous_rows() -> None:
    csv_data = b"archivo,nombre,sku\nuno.png,Valido,OK-01\ndos.png,Invalido,../../etc\n"
    with TestClient(create_app()) as client:
        batch_id, image_ids = _batch_with_images(client)
        response = client.post(
            f"/api/v1/batches/{batch_id}/metadata-csv",
            files={"file": ("productos.csv", csv_data, "text/csv")},
        )
        first = client.get(f"/api/v1/images/{image_ids[0]}").json()

    assert response.status_code == 422
    assert first["product_name"] is None
    assert first["sku"] is None


def test_csv_rejects_unknown_and_duplicate_filenames() -> None:
    with TestClient(create_app()) as client:
        batch_id, _image_ids = _batch_with_images(client)
        unknown = client.post(
            f"/api/v1/batches/{batch_id}/metadata-csv",
            files={"file": ("productos.csv", b"archivo,nombre,sku\notra.png,Otra,OTRA\n", "text/csv")},
        )

        duplicate_batch_id, _duplicate_ids = _batch_with_images(client, duplicate_names=True)
        ambiguous = client.post(
            f"/api/v1/batches/{duplicate_batch_id}/metadata-csv",
            files={"file": ("productos.csv", b"archivo,nombre,sku\nuno.png,Uno,UNO\n", "text/csv")},
        )

    assert unknown.status_code == 422
    assert ambiguous.status_code == 409


def test_csv_requires_utf8_and_expected_headers() -> None:
    with TestClient(create_app()) as client:
        batch_id, _image_ids = _batch_with_images(client)
        bad_encoding = client.post(
            f"/api/v1/batches/{batch_id}/metadata-csv",
            files={"file": ("productos.csv", b"archivo,nombre,sku\nuno.png,\xff,UNO\n", "text/csv")},
        )
        bad_headers = client.post(
            f"/api/v1/batches/{batch_id}/metadata-csv",
            files={"file": ("productos.csv", b"file,name,sku\nuno.png,Uno,UNO\n", "text/csv")},
        )

    assert bad_encoding.status_code == 400
    assert bad_headers.status_code == 422
