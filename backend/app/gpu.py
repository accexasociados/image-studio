import gc
from functools import lru_cache

from app.contracts import GpuInfo


@lru_cache
def detect_gpu() -> GpuInfo:
    """No falla si torch no está instalado (modo stub o instalación sin el extra `ml`)."""
    try:
        import torch
    except ImportError:
        return GpuInfo(available=False)
    if not torch.cuda.is_available():
        return GpuInfo(available=False)
    props = torch.cuda.get_device_properties(0)
    return GpuInfo(available=True, name=props.name, vram_mb=props.total_memory // (1024 * 1024))


def release_gpu_memory() -> None:
    """Libera referencias y caché CUDA sin hacer obligatorio el extra `ml`."""
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
