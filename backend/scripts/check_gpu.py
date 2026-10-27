"""Verifica CUDA, la GPU y que los cálculos en FP32 den resultados válidos.

Uso: python -m scripts.check_gpu
"""

import sys
import time


def main() -> int:
    try:
        import torch
    except ImportError:
        print("torch no está instalado. Ver README: instalación con CUDA.")
        return 1

    print(f"torch {torch.__version__} | CUDA del build: {torch.version.cuda}")
    if not torch.cuda.is_available():
        print("CUDA no disponible: el proceso correrá en CPU (lento). Revisa el driver con nvidia-smi.")
        return 1

    props = torch.cuda.get_device_properties(0)
    print(
        f"GPU: {props.name} | VRAM: {props.total_memory // (1024 * 1024)} MB | "
        f"compute capability {props.major}.{props.minor}"
    )

    device = torch.device("cuda")
    x = torch.randn(1, 3, 1024, 1024, device=device)
    conv = torch.nn.Conv2d(3, 64, 3, padding=1).to(device)
    torch.cuda.synchronize()
    started = time.perf_counter()
    with torch.no_grad():
        for _ in range(10):
            y = conv(x)
    torch.cuda.synchronize()
    elapsed_ms = (time.perf_counter() - started) * 100
    if not torch.isfinite(y).all():
        print("FP32: resultado inválido (NaN/Inf).")
        return 1
    print(f"FP32: OK ({elapsed_ms:.1f} ms por convolución 1024x1024)")

    with torch.no_grad():
        y_half = conv.half()(x.half())
    status = "OK" if torch.isfinite(y_half).all() else "NaN/Inf"
    print(f"FP16: {status} (el proceso usa FP32 por defecto; la serie GTX 16xx es inestable en FP16)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
