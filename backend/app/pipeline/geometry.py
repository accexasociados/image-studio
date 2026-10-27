"""Rotación y recorte elegidos en la web (ProcessOptions.rotate / crop) antes de segmentar.

La máscara se guarda siempre en coordenadas de la foto original (con EXIF aplicado), así el pincel
de la web y `mask_override` no dependen del recorte: `forward` la lleva al encuadre y `restore` la
devuelve al original."""

from dataclasses import dataclass
from typing import TypeVar

import numpy as np
import numpy.typing as npt

from app.contracts.options import CropBox, Rotation

_T = TypeVar("_T", bound=np.generic)


@dataclass(frozen=True)
class Geometry:
    rotate: Rotation
    # Recorte en píxeles de la imagen ya rotada: (top, bottom, left, right).
    box: tuple[int, int, int, int]
    rotated_shape: tuple[int, int]

    @property
    def is_identity(self) -> bool:
        top, bottom, left, right = self.box
        return self.rotate == 0 and (top, left) == (0, 0) and (bottom, right) == self.rotated_shape


def plan(shape: tuple[int, int], rotate: Rotation, crop: CropBox | None) -> Geometry:
    height, width = shape
    rotated = (width, height) if rotate in (90, 270) else (height, width)
    if crop is None:
        return Geometry(rotate, (0, rotated[0], 0, rotated[1]), rotated)
    top = min(max(round(crop.y * rotated[0]), 0), rotated[0] - 1)
    left = min(max(round(crop.x * rotated[1]), 0), rotated[1] - 1)
    bottom = min(max(round((crop.y + crop.height) * rotated[0]), top + 1), rotated[0])
    right = min(max(round((crop.x + crop.width) * rotated[1]), left + 1), rotated[1])
    return Geometry(rotate, (top, bottom, left, right), rotated)


def _rotate(array: npt.NDArray[_T], degrees: int) -> npt.NDArray[_T]:
    # `rotate` es en sentido horario; np.rot90 gira en sentido antihorario con k > 0.
    return np.ascontiguousarray(np.rot90(array, k=-(degrees // 90)))


def forward(array: npt.NDArray[_T], geometry: Geometry) -> npt.NDArray[_T]:
    """Original -> encuadre (imagen o máscara)."""
    top, bottom, left, right = geometry.box
    return np.ascontiguousarray(_rotate(array, geometry.rotate)[top:bottom, left:right])


def restore(alpha: npt.NDArray[np.float32], geometry: Geometry) -> npt.NDArray[np.float32]:
    """Máscara del encuadre -> coordenadas del original (fuera del recorte queda en 0)."""
    top, bottom, left, right = geometry.box
    canvas = np.zeros(geometry.rotated_shape, np.float32)
    canvas[top:bottom, left:right] = alpha
    return np.ascontiguousarray(np.rot90(canvas, k=geometry.rotate // 90)).astype(np.float32)
