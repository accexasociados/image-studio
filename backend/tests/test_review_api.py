"""Fase 6: variante elegida al aprobar, acciones en bloque, miniaturas y rotación/recorte."""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app.contracts import AppSettings, CropBox, ProcessOptions, ProcessResult
from app.main import create_app
from app.pipeline.geometry import forward, plan, restore
from app.queue import get_job_queue
from app.queue.worker import PipelineProcessor, Worker
from app.storage import get_storage


def _png_bytes(size: tuple[int, int] = (40, 20)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, "red").save(stream, format="PNG")
    return stream.getvalue()


def _run_all() -> None:
    worker = Worker(
        worker_id="review-test",
        queue=get_job_queue(),
        storage=get_storage(),
        processor=PipelineProcessor(),
        release_memory=lambda: None,
    )
    while worker.run_once():
        pass


def _batch(client: TestClient, count: int = 1, **options: object) -> tuple[str, list[str]]:
    batch_id = client.post(
        "/api/v1/batches",
        json={"name": "Revisión", "default_options": {"presets": ["storefront"], **options}},
    ).json()["id"]
    response = client.post(
        f"/api/v1/batches/{batch_id}/images",
        files=[("files", (f"pieza-{index}.png", _png_bytes(), "image/png")) for index in range(count)],
    )
    _run_all()
    return batch_id, [image["id"] for image in response.json()]


def _zip_names(client: TestClient, batch_id: str) -> list[str]:
    response = client.get(f"/api/v1/batches/{batch_id}/download/storefront.zip")
    assert response.status_code == 200
    return sorted(ZipFile(BytesIO(response.content)).namelist())


def test_selected_variant_is_the_only_one_exported_and_keeps_the_plain_name() -> None:
    with TestClient(create_app()) as client:
        batch_id, [image_id] = _batch(client, generate_both_layer_variants=True)
        client.patch(f"/api/v1/images/{image_id}", json={"sku": "DRG-01"})

        client.post(f"/api/v1/images/{image_id}/approve")
        both = _zip_names(client, batch_id)
        approved = client.post(f"/api/v1/images/{image_id}/approve", json={"variant": "smooth"})
        chosen = _zip_names(client, batch_id)

    assert both == ["DRG-01.webp", "DRG-01_smooth.webp"]
    assert approved.json()["selected_variant"] == "smooth"
    assert chosen == ["DRG-01.webp"]


def test_approving_a_missing_variant_is_rejected() -> None:
    with TestClient(create_app()) as client:
        _batch_id, [image_id] = _batch(client)
        response = client.post(f"/api/v1/images/{image_id}/approve", json={"variant": "smooth"})

    assert response.status_code == 422


def test_reprocess_clears_the_selected_variant() -> None:
    with TestClient(create_app()) as client:
        _batch_id, [image_id] = _batch(client, generate_both_layer_variants=True)
        client.post(f"/api/v1/images/{image_id}/approve", json={"variant": "smooth"})
        response = client.post(f"/api/v1/images/{image_id}/reprocess")

    assert response.json()["selected_variant"] is None


def test_bulk_approve_and_reprocess_skip_images_still_in_progress() -> None:
    with TestClient(create_app()) as client:
        batch_id, [*image_ids, extra] = _batch(client, count=3)
        client.post(f"/api/v1/images/{extra}/reprocess")  # vuelve a quedar pendiente

        approved = client.post(
            f"/api/v1/batches/{batch_id}/images/approve", json={"image_ids": [*image_ids, extra]}
        )
        reprocessed = client.post(
            f"/api/v1/batches/{batch_id}/images/reprocess",
            json={"image_ids": image_ids, "options": {"presets": ["instagram_square"], "rotate": 90}},
        )
        foreign = client.post(f"/api/v1/batches/{batch_id}/images/approve", json={"image_ids": ["otra"]})

    assert [image["status"] for image in approved.json()] == ["approved", "approved", "pending"]
    assert {image["status"] for image in reprocessed.json()} == {"pending"}
    assert {image["options_override"]["rotate"] for image in reprocessed.json()} == {90}
    assert foreign.status_code == 404


def test_thumbnails_are_resized_cached_and_limited_to_fixed_widths() -> None:
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Miniaturas"}).json()["id"]
        original = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("grande.png", _png_bytes((1000, 500)), "image/png")},
        ).json()[0]["original_path"]

        thumb = client.get(f"/api/v1/files/{original}", params={"w": 320})
        again = client.get(f"/api/v1/files/{original}", params={"w": 320})
        invalid = client.get(f"/api/v1/files/{original}", params={"w": 333})
        direct = client.get(f"/api/v1/files/thumbs/w320/{original}.webp")

    assert thumb.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(thumb.content)) as rendered:
        assert rendered.size == (320, 160)
    assert again.content == thumb.content
    assert invalid.status_code == 422
    assert direct.status_code == 404


def test_geometry_round_trip_keeps_the_mask_in_original_coordinates() -> None:
    original = np.zeros((40, 60), np.float32)
    original[10:20, 30:50] = 1.0
    for rotate in (0, 90, 180, 270):
        geometry = plan((40, 60), rotate, CropBox(x=0.1, y=0.1, width=0.8, height=0.8))
        framed = forward(original, geometry)
        assert framed.shape == ((32, 48) if rotate in (0, 180) else (48, 32))
        restored = restore(framed, geometry)
        assert restored.shape == (40, 60)
        np.testing.assert_array_equal(restored[10:20, 30:50], 1.0)


def test_rotate_90_is_clockwise() -> None:
    image = np.zeros((2, 3), np.uint8)
    image[0, 0] = 1  # esquina superior izquierda
    rotated = forward(image, plan((2, 3), 90, None))
    assert rotated.shape == (3, 2)
    assert rotated[0, 1] == 1  # pasa a la esquina superior derecha


def test_crop_box_must_stay_inside_the_photo() -> None:
    with pytest.raises(ValidationError):
        ProcessOptions(crop=CropBox(x=0.5, y=0, width=0.6, height=1))


def test_stub_pipeline_applies_rotation_and_crop() -> None:
    with TestClient(create_app()) as client:
        _batch_id, [image_id] = _batch(
            client,
            presets=["original_hd"],
            rotate=90,
            crop={"x": 0, "y": 0, "width": 1, "height": 0.5},
        )
        image = client.get(f"/api/v1/images/{image_id}").json()

    # Original 40x20 -> girado 20x40 -> mitad superior 20x20 -> lado mayor del preset.
    output = image["outputs"][0]
    assert output["width"] == output["height"]


class _MaskSpyProcessor:
    """Como el proceso real: devuelve una máscara nueva y registra si recibió `mask_override`."""

    def __init__(self) -> None:
        self.overrides: list[Path | None] = []

    def __call__(
        self,
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult:
        self.overrides.append(mask_override)
        result = PipelineProcessor()(
            input_path, options, out_dir, base_name=base_name, mask_override=None, settings=settings
        )
        mask = out_dir / f"{base_name}_mask.png"
        Image.new("L", (40, 20), 255).save(mask)
        return result.model_copy(update={"mask_path": str(mask)})


def test_only_hand_edited_masks_are_reused_when_reprocessing() -> None:
    spy = _MaskSpyProcessor()
    worker = Worker(
        worker_id="mask-test",
        queue=get_job_queue(),
        storage=get_storage(),
        processor=spy,
        release_memory=lambda: None,
    )
    with TestClient(create_app()) as client:
        batch_id = client.post("/api/v1/batches", json={"name": "Máscaras"}).json()["id"]
        image_id = client.post(
            f"/api/v1/batches/{batch_id}/images",
            files={"files": ("pieza.png", _png_bytes(), "image/png")},
        ).json()[0]["id"]
        worker.run_once()
        client.post(f"/api/v1/images/{image_id}/reprocess")
        worker.run_once()
        stream = BytesIO()
        Image.new("L", (40, 20), 128).save(stream, format="PNG")
        edited = client.put(
            f"/api/v1/images/{image_id}/mask", files={"file": ("m.png", stream.getvalue(), "image/png")}
        )
        worker.run_once()
        client.post(f"/api/v1/images/{image_id}/reprocess", json={"shadow": "soft"})
        worker.run_once()
        discarded = client.delete(f"/api/v1/images/{image_id}/mask")
        worker.run_once()

    # 1.º proceso y reproceso: BiRefNet; tras el pincel (y en el reproceso siguiente) se usa la
    # corrección; al descartarla vuelve la segmentación automática.
    assert [override is not None for override in spy.overrides] == [False, False, True, True, False]
    assert edited.json()["mask_edited"] is True
    assert discarded.json()["mask_edited"] is False
