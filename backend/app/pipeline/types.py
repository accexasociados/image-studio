import numpy as np
import numpy.typing as npt

# Imagen RGB float32 en [0, 1] (H, W, 3) y máscara alfa float32 en [0, 1] (H, W).
FloatImage = npt.NDArray[np.float32]
Alpha = npt.NDArray[np.float32]
RgbImage = npt.NDArray[np.uint8]


def to_float(image: RgbImage) -> FloatImage:
    return (image.astype(np.float32) / 255.0).astype(np.float32)


def to_uint8(image: FloatImage) -> RgbImage:
    result: RgbImage = np.clip(np.rint(image * 255.0), 0, 255).astype(np.uint8)
    return result


def luminance(image: FloatImage) -> npt.NDArray[np.float32]:
    weights = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    return (image @ weights).astype(np.float32)
