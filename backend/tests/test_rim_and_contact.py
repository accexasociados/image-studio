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


def test_enhance_keeps_the_piece_shadows_dark() -> None:
    from app.pipeline.color import enhance

    image = np.zeros((100, 100, 3), np.float32)
    image[:, :50] = 0.08  # humo negro / lado en sombra
    image[:, 50:] = 0.5
    image[0, 0] = 0.0
    image[0, 99] = 0.97
    alpha = np.ones((100, 100), np.float32)
    result = enhance(image, alpha, 1.0)
    # Las sombras no se aclaran (antes la curva las dejaba en 0,06) y los medios tonos sí.
    assert result[50, 20].mean() < 0.045
    assert result[50, 80].mean() > 0.53


def test_a_raised_arm_casts_a_fainter_shadow_than_the_grounded_body() -> None:
    from app.pipeline.scene import _cast_shadow, _Placed

    alpha = np.zeros((600, 600), np.float32)
    alpha[100:500, 280:320] = 1.0  # cuerpo apoyado en el piso (fila 499)
    alpha[120:160, 80:280] = 1.0  # brazo alto hacia la izquierda
    placed = _Placed(np.zeros((600, 600, 3), np.float32), alpha, 100, 499, 280, 320)
    shadow = _cast_shadow(placed, (600, 600), 1.0, "left")
    # Antes el brazo dejaba una mancha suelta tan oscura como la sombra junto a la base.
    assert shadow[:, :250].max() < shadow[:, 250:330].max() * 0.75
