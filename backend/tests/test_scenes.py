"""Escenas de la Fase 11: la pieza apoyada en estudio, pedestal o foto de fondo."""

from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.contracts import AppSettings, ProcessOptions
from app.main import create_app
from app.pipeline.compose import Crop
from app.pipeline.run import process_image
from app.pipeline.scene import BackgroundPhoto, SceneSpec, brand_colors, render_scene

W, H = 400, 500


def _crop() -> Crop:
    """Pieza naranja rectangular con base plana, ya recortada."""
    alpha = np.zeros((300, 200), np.float32)
    alpha[20:280, 40:160] = 1.0
    image = np.empty((300, 200, 3), np.float32)
    image[:] = (0.9, 0.45, 0.1)
    return Crop(image, alpha)


def _piece_rows(result: np.ndarray) -> tuple[int, int]:
    orange = (result[..., 0] > 0.8) & (result[..., 2] < 0.2)
    rows = np.flatnonzero(orange.any(axis=1))
    return int(rows[0]), int(rows[-1])


def test_studio_rests_piece_on_floor_with_contact_shadow() -> None:
    spec = SceneSpec(kind="studio", reflection=0.0)
    with_shadow = render_scene(_crop(), (W, H), 0.8, spec, shadow_strength=1.0)
    without_shadow = render_scene(_crop(), (W, H), 0.8, spec, shadow_strength=0.0)

    top, bottom = _piece_rows(with_shadow)
    assert abs(bottom - H * 0.80) <= 2
    assert top >= H * 0.06
    # Justo al lado de la base la sombra oscurece el piso; sin sombra no.
    _rows, columns = np.nonzero((with_shadow[..., 0] > 0.8) & (with_shadow[..., 2] < 0.2))
    beside = (bottom - 1, int(columns.max()) + 6)
    assert with_shadow[beside].mean() < without_shadow[beside].mean() - 0.05
    # Arriba, lejos de la pieza, la pared queda casi blanca.
    assert with_shadow[5, 5].mean() > 0.9


def test_studio_reflection_appears_below_the_base() -> None:
    plain = render_scene(_crop(), (W, H), 0.8, SceneSpec(kind="studio", reflection=0.0), 0.0)
    glossy = render_scene(_crop(), (W, H), 0.8, SceneSpec(kind="studio", reflection=0.3), 0.0)
    _top, bottom = _piece_rows(plain)
    below = (bottom + 8, W // 2)
    # El reflejo naranja tiñe el piso: más rojo que azul.
    assert glossy[below][0] - glossy[below][2] > plain[below][0] - plain[below][2] + 0.05


def test_pedestal_puts_piece_on_top_of_the_base() -> None:
    spec = SceneSpec(kind="pedestal", pedestal=(200, 60, 60))
    result = render_scene(_crop(), (W, H), 0.8, spec, shadow_strength=1.0)
    _top, bottom = _piece_rows(result)
    # Apoyada un poco por delante del centro de la tapa.
    assert H * 0.70 <= bottom <= H * 0.70 + 8
    # Debajo de la pieza está el cuerpo del pedestal (rojizo), no el piso.
    body = result[int(H * 0.76), W // 2]
    assert body[0] > body[1] + 0.2


def test_brand_colors_lighten_the_wall() -> None:
    wall, floor = brand_colors((100, 150, 200))
    assert floor == (100, 150, 200)
    assert all(w > f for w, f in zip(wall, floor, strict=True))


def test_photo_background_anchors_piece_on_marked_floor(tmp_path: Path) -> None:
    background = np.zeros((600, 800, 3), np.uint8)
    background[:] = (40, 90, 160)
    path = tmp_path / "mesa.png"
    Image.fromarray(background).save(path)
    spec = SceneSpec(
        kind="photo", background=BackgroundPhoto(path=path, floor_y=0.75, center_x=0.5, piece_height=0.5)
    )

    result = render_scene(_crop(), (W, H), 0.8, spec, shadow_strength=1.0)

    _top, bottom = _piece_rows(result)
    assert abs(bottom - H * 0.75) <= 3
    assert np.allclose(result[3, 3], np.array([40, 90, 160]) / 255, atol=0.01)


def test_photo_scene_without_background_fails() -> None:
    with pytest.raises(ValueError, match="foto de fondo"):
        render_scene(_crop(), (W, H), 0.8, SceneSpec(kind="photo"), 1.0)


@pytest.fixture
def real_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIPELINE_MODE", "real")
    monkeypatch.setenv("DEVICE", "cpu")
    get_settings.cache_clear()


def _source(tmp_path: Path) -> tuple[Path, Path]:
    image = np.full((400, 300, 3), 180, np.uint8)
    alpha = np.zeros((400, 300), np.uint8)
    cv2.rectangle(alpha, (90, 60), (210, 340), 255, -1)
    image[alpha > 0] = (230, 110, 30)
    source, mask = tmp_path / "pieza.png", tmp_path / "mask.png"
    Image.fromarray(image).save(source)
    Image.fromarray(alpha).save(mask)
    return source, mask


def test_pipeline_uses_scene_from_options_and_4x5_hd(tmp_path: Path, real_mode: None) -> None:
    source, mask = _source(tmp_path)
    settings = AppSettings()
    settings.pipeline.upscale_model = "lanczos"
    settings.export.scene.style = "white"

    result = process_image(
        source,
        ProcessOptions(presets=["original_hd"], scene="studio", upscale=1),
        tmp_path / "out",
        base_name="P",
        mask_override=mask,
        settings=settings,
    )

    hd = result.outputs[0]
    assert hd.width * 5 == hd.height * 4
    with Image.open(hd.path) as rendered:
        corner = np.asarray(rendered.convert("RGB"))[-5, -5]
    # El piso del estudio no es blanco puro.
    assert corner.max() < 250


def test_pipeline_photo_scene_needs_a_background(tmp_path: Path, real_mode: None) -> None:
    source, mask = _source(tmp_path)
    settings = AppSettings()
    settings.export.scene.style = "photo"
    with pytest.raises(ValueError, match="fondo"):
        process_image(
            source, ProcessOptions(), tmp_path / "out", base_name="P", mask_override=mask, settings=settings
        )


def _png() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (64, 48), (120, 90, 60)).save(stream, format="PNG")
    return stream.getvalue()


def test_background_library_crud_and_default() -> None:
    with TestClient(create_app()) as client:
        created = client.post(
            "/api/v1/backgrounds", files={"file": ("mesa.png", _png(), "image/png")}, data={"name": "Mesa"}
        )
        assert created.status_code == 201, created.text
        background = created.json()
        assert (background["name"], background["width"], background["height"]) == ("Mesa", 64, 48)
        assert client.get(background["url"]).status_code == 200
        scene = client.get("/api/v1/settings").json()["export"]["scene"]
        assert scene["default_background_id"] == background["id"]

        patched = client.patch(f"/api/v1/backgrounds/{background['id']}", json={"floor_y": 0.7})
        assert patched.json()["floor_y"] == 0.7
        assert client.patch(f"/api/v1/backgrounds/{background['id']}", json={"floor_y": 2}).status_code == 422
        assert [item["id"] for item in client.get("/api/v1/backgrounds").json()] == [background["id"]]

        assert client.delete(f"/api/v1/backgrounds/{background['id']}").status_code == 204
        assert client.get("/api/v1/backgrounds").json() == []
        scene = client.get("/api/v1/settings").json()["export"]["scene"]
        assert scene["default_background_id"] is None


def test_background_upload_rejects_non_images() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/backgrounds", files={"file": ("x.png", b"no", "image/png")})
        assert response.status_code == 415
