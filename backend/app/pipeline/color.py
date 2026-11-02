"""Corrección de color suave: balance de blancos tomando el fondo como referencia neutra y
exposición de la pieza. Nada de saturación ni contraste agresivos (eso delata el retoque)."""

from dataclasses import dataclass

import cv2
import numpy as np

from app.pipeline.types import Alpha, FloatImage, luminance


@dataclass(frozen=True)
class ColorParams:
    # Fracción de la corrección de blancos que se aplica (1 = neutralizar del todo el fondo).
    white_balance_strength: float = 0.85
    max_channel_gain: float = 1.25
    # Si el fondo tiene más croma que esto, no es una referencia neutra (p. ej. cajas de colores).
    max_background_chroma: float = 0.25
    # La parte más clara de la pieza (percentil) se lleva hacia este valor, con un tope de ganancia.
    exposure_percentile: float = 99.0
    exposure_target: float = 0.94
    max_exposure_gain: float = 1.35
    # Fondo claro (percentil) de una foto bien expuesta: con este valor no hace falta aclarar más.
    background_percentile: float = 90.0
    background_target: float = 0.92


@dataclass(frozen=True)
class ColorResult:
    image: FloatImage
    gains: tuple[float, float, float]
    exposure_gain: float
    white_balance_applied: bool


def _background_reference(image: FloatImage, alpha: Alpha) -> FloatImage | None:
    """Píxeles claros del fondo (la cartulina), lejos de la pieza."""
    background = alpha < 0.02
    if background.sum() < 500:
        return None
    lum = luminance(image)
    # La mitad más clara del fondo: la cartulina, no la mesa oscura de abajo.
    bright = lum >= np.percentile(lum[background], 50)
    candidates = image[background & bright]
    if candidates.shape[0] < 500:
        return None
    return candidates


def white_balance_gains(
    image: FloatImage, alpha: Alpha, params: ColorParams
) -> tuple[float, float, float] | None:
    reference = _background_reference(image, alpha)
    if reference is None:
        return None
    mean = np.median(reference, axis=0)
    gray = float(mean.mean())
    if gray <= 0.05:
        return None
    chroma = float((mean.max() - mean.min()) / max(gray, 1e-6))
    if chroma > params.max_background_chroma:
        return None
    raw = gray / np.maximum(mean, 1e-6)
    gains = 1.0 + (raw - 1.0) * params.white_balance_strength
    clipped = np.clip(gains, 1 / params.max_channel_gain, params.max_channel_gain)
    return float(clipped[0]), float(clipped[1]), float(clipped[2])


def _downsample(image: FloatImage, alpha: Alpha, long_side: int = 1024) -> tuple[FloatImage, Alpha]:
    scale = long_side / max(alpha.shape)
    if scale >= 1:
        return image, alpha
    size = (round(alpha.shape[1] * scale), round(alpha.shape[0] * scale))
    small_image = cv2.resize(image, size, interpolation=cv2.INTER_AREA).astype(np.float32)
    return small_image, cv2.resize(alpha, size, interpolation=cv2.INTER_AREA).astype(np.float32)


def correct_color(
    image: FloatImage,
    alpha: Alpha,
    *,
    white_balance: bool,
    params: ColorParams | None = None,
    apply_to: FloatImage | None = None,
) -> ColorResult:
    """Calcula la corrección sobre una copia reducida de la foto completa (fondo incluido) y la
    aplica a `apply_to` (p. ej. el recorte de la pieza) o, si no se da, a la foto completa."""
    params = params or ColorParams()
    small_image, small_alpha = _downsample(image, alpha)
    gains = white_balance_gains(small_image, small_alpha, params) if white_balance else None
    gain_vector = np.array(gains or (1.0, 1.0, 1.0), dtype=np.float32)

    piece = small_alpha > 0.5
    exposure_gain = 1.0
    if piece.sum() > 100:
        bright = float(np.percentile(luminance(small_image * gain_vector)[piece], params.exposure_percentile))
        if 0.05 < bright < params.exposure_target:
            exposure_gain = min(params.exposure_target / bright, params.max_exposure_gain)
        # La pieza no siempre tiene blanco (un Gengar morado y negro): llevar su parte más clara a 0,94 la
        # aclaraba un 28 % aunque la foto estuviera bien expuesta. El fondo claro dice cuánta luz tenía la
        # foto de verdad, así que la ganancia no pasa de lo que necesita el fondo para verse bien expuesto.
        background = small_alpha < 0.02
        if background.sum() > 500:
            card = float(
                np.percentile(luminance(small_image * gain_vector)[background], params.background_percentile)
            )
            if card > 0.05:
                exposure_gain = min(exposure_gain, max(params.background_target / card, 1.0))

    target = image if apply_to is None else apply_to
    corrected = target * (gain_vector * exposure_gain)

    return ColorResult(
        image=np.clip(corrected, 0.0, 1.0).astype(np.float32),
        gains=gains or (1.0, 1.0, 1.0),
        exposure_gain=exposure_gain,
        white_balance_applied=gains is not None,
    )


@dataclass(frozen=True)
class EnhanceParams:
    """Realce tipo foto de producto (Fase 12). Con fuerza 1 la pieza queda como en una foto de estudio:
    blancos limpios, negros firmes, colores vivos y algo de contraste local. Con 0 no se toca."""

    black_percentile: float = 1.0
    black_target: float = 0.03
    white_percentile: float = 99.5
    white_target: float = 0.97
    max_white_gain: float = 1.15
    # Curva de tonos: con fuerza 1, gamma 0,8 aclara los medios tonos (blancos en sombra, colores) sin
    # tocar el negro ni el blanco puros. Es lo que más acerca una foto de celular a una de estudio.
    midtone_gamma: float = 0.8
    # Por debajo de `shadow_floor` la curva no actúa; entre los dos límites entra de forma gradual.
    shadow_floor: float = 0.06
    shadow_ceiling: float = 0.4
    # Aumento de saturación que crece en los colores apagados y casi no toca los ya saturados.
    vibrance: float = 0.45
    # Peso del detalle de luminancia (máscara de enfoque con radio del 1 % del lado mayor).
    local_contrast: float = 0.35
    # Reflejos: entorno con el que se miden (fracción del lado mayor), cuánto pueden crecer (1 = igual que
    # en la foto) y desde qué exceso de luminancia un píxel cuenta como reflejo.
    glint_radius: float = 0.01
    glint_gain: float = 1.0
    glint_threshold: float = 0.05


def enhance(
    image: FloatImage, alpha: Alpha, strength: float, params: EnhanceParams | None = None
) -> FloatImage:
    """Niveles, viveza y contraste local medidos solo dentro de la pieza (`alpha > 0.5`)."""
    params = params or EnhanceParams()
    piece = alpha > 0.5
    if strength <= 0 or piece.sum() < 100:
        return image
    lum = luminance(image)
    low = float(np.percentile(lum[piece], params.black_percentile))
    high = float(np.percentile(lum[piece], params.white_percentile))
    target_low = low - max(low - params.black_target, 0.0) * strength
    target_high = high + max(min(params.white_target, high * params.max_white_gain) - high, 0.0) * strength
    result = (image - low) * ((target_high - target_low) / max(high - low, 1e-3)) + target_low
    gamma = 1.0 - (1.0 - params.midtone_gamma) * strength
    result = np.clip(result, 0.0, 1.0)
    # La curva solo aclara de los medios tonos hacia arriba: las sombras propias de la pieza (el lado en
    # sombra, un negro de base) conservan su valor y la pieza no pierde volumen ni el negro se vuelve gris.
    lifted = np.power(result, gamma)
    shade = luminance(result)[..., None]
    keep = np.clip((shade - params.shadow_floor) / (params.shadow_ceiling - params.shadow_floor), 0.0, 1.0)
    keep = keep * keep * (3.0 - 2.0 * keep)
    result = result + (lifted - result) * keep

    lum = luminance(np.clip(result, 0.0, 1.0))[..., None]
    saturation = result.max(axis=-1, keepdims=True) - result.min(axis=-1, keepdims=True)
    # En los oscuros casi neutros (negros con un reflejo de color) la viveza solo aviva el tinte: se apaga.
    dark_weight = np.clip((lum - 0.12) / 0.25, 0.0, 1.0)
    boost = params.vibrance * strength * (1.0 - np.clip(saturation, 0.0, 1.0)) * dark_weight
    result = lum + (result - lum) * (1.0 + boost)

    # Banda media de detalle: realza el volumen de la pieza pero deja fuera lo más fino (ruido del JPEG
    # y la textura que inventa el modelo al agrandar), que con una máscara de enfoque normal se veía rayado.
    size = max(image.shape[:2])
    base = luminance(np.clip(result, 0.0, 1.0))
    fine = cv2.GaussianBlur(base, (0, 0), max(size * 0.003, 1.0))
    detail = fine - cv2.GaussianBlur(base, (0, 0), size * 0.015)
    result = result + (detail * params.local_contrast * strength)[..., None]
    result = _keep_glints(image, np.clip(result, 0.0, 1.0), params)
    enhanced: FloatImage = np.clip(result, 0.0, 1.0).astype(np.float32)
    return enhanced


def _glint(lum: np.ndarray, sigma: float) -> np.ndarray:
    """Cuánto sobresale cada píxel claro sobre su entorno: los reflejos de la luz en el plástico."""
    excess: np.ndarray = np.clip(lum - cv2.GaussianBlur(lum, (0, 0), sigma), 0.0, None)
    return excess


def _keep_glints(before: FloatImage, after: FloatImage, params: EnhanceParams) -> FloatImage:
    """Los reflejos quedan con la intensidad que tenían en la foto. La curva, el contraste local y la
    exposición los subían más del 40 % y la pieza parecía brillante donde en la foto no lo era (Gengar,
    calabaza del Snoopy). Solo se recorta lo que el realce agregó por encima del reflejo original."""
    sigma = max(max(before.shape[:2]) * params.glint_radius, 1.0)
    glint_before = _glint(luminance(before), sigma)
    glint_after = _glint(luminance(after), sigma)
    added = np.clip(glint_after - glint_before * params.glint_gain, 0.0, None)
    # Solo donde la foto ya tenía un reflejo; el resto del detalle (bordes, líneas de capa) no se toca.
    weight = np.clip(glint_before / params.glint_threshold, 0.0, 1.0)
    kept: FloatImage = (after - (added * weight)[..., None]).astype(np.float32)
    return kept


def sharpen(image: FloatImage, strength: float) -> FloatImage:
    """Enfoque final (máscara de enfoque) sobre la imagen ya compuesta, a su tamaño de salida.

    Con fuerza 0,6 (el valor por defecto) la nitidez de una foto de celular agrandada queda cerca de la de
    una foto de catálogo (medido en la Fase 12). El radio crece con el lienzo para que el efecto se vea
    igual en 1080 px que en 2000 px. Sobre el fondo liso y las sombras suaves casi no actúa."""
    if strength <= 0:
        return image
    radius = 1.2 * max(image.shape[:2]) / 1350
    blurred = cv2.GaussianBlur(image, (0, 0), max(radius, 0.8))
    detail = image - blurred
    # El lado claro del detalle pesa la mitad: los bordes ganan definición por el lado oscuro y los
    # reflejos no se encienden (con el mismo peso el enfoque los subía otro 13 %).
    detail = np.where(detail > 0, detail * _SHARPEN_BRIGHT_SIDE, detail)
    sharpened: FloatImage = np.clip(image + detail * (_SHARPEN_AMOUNT * strength), 0.0, 1.0).astype(
        np.float32
    )
    return sharpened


_SHARPEN_BRIGHT_SIDE = 0.5
_SHARPEN_AMOUNT = 2.2
