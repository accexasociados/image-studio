"""Fase 12: borde sin el tinte del fondo y sombra de contacto que no asoma por delante de la base."""

import numpy as np

from app.pipeline.compose import Crop, decontaminate_edges
from app.pipeline.scene import SceneSpec, render_scene


def test_rim_takes_the_piece_color_not_the_background_tint() -> None:
    image = np.zeros((80, 80, 3), np.float32)
    image[:] = (0.35, 0.65, 0.66)  # tela turquesa
    alpha = np.zeros((80, 80), np.float32)
    alpha[20:60, 20:60] = 1.0
    image[20:60, 20:60] = (0.07, 0.08, 0.10)  # base negra
    image[57:60, 20:60] = (0.06, 0.11, 0.12)  # borde teñido por la tela, con alfa 1
    result = decontaminate_edges(image, alpha)
    tint_before = image[58, 40, 1] - image[58, 40, 0]
    tint_after = result[58, 40, 1] - result[58, 40, 0]
    assert tint_after < tint_before * 0.5
    # El interior no cambia.
    assert np.allclose(result[40, 40], image[40, 40])


def test_contact_shadow_does_not_spill_in_front_of_the_base() -> None:
    alpha = np.zeros((300, 200), np.float32)
    alpha[20:280, 40:160] = 1.0
    image = np.empty((300, 200, 3), np.float32)
    image[:] = (0.9, 0.45, 0.1)
    spec = SceneSpec(
        kind="studio", reflection=0.0, shadow_side="none", floor=(253, 253, 253), wall=(253, 253, 253)
    )
    lit = render_scene(Crop(image, alpha), (400, 500), 0.8, spec, shadow_strength=1.0)
    flat = render_scene(Crop(image, alpha), (400, 500), 0.8, spec, shadow_strength=0.0)
    orange = (lit[..., 0] > 0.8) & (lit[..., 2] < 0.2)
    bottom = int(np.flatnonzero(orange.any(1))[-1])
    # 12 px por delante de la base el piso casi no se oscurece (antes quedaba una franja que la hacía flotar).
    assert flat[bottom + 12, 200].mean() - lit[bottom + 12, 200].mean() < 0.05
