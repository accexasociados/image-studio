"""Punto de entrada del proceso de imagen. No depende de FastAPI ni de la BD: lo llaman el worker,
la CLI y cualquier otra entrada. Los ajustes (Ajustes > Modelos, Formatos, Calidad) llegan como
parámetro en `settings`.

Modo `stub` (PIPELINE_MODE=stub): pega la foto sobre el lienzo de cada formato sin IA, para que la
API y la web avancen sin GPU."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from app.config import get_settings
from app.contracts import PRESETS, AppSettings, LayerLines, OutputFile, Preset, ProcessOptions, ProcessResult
from app.pipeline.color import correct_color
from app.pipeline.compose import Crop, compose_on_canvas, crop_to_piece, decontaminate_edges, piece_bounds
from app.pipeline.export import encode, output_path, resolve_preset
from app.pipeline.layers import smooth_layer_lines
from app.pipeline.quality import review_reasons
from app.pipeline.segment import SegmentationParams, load_birefnet, segment
from app.pipeline.shadow import ShadowParams, resolve_shadow
from app.pipeline.types import Alpha, FloatImage, to_float, to_uint8
from app.pipeline.upscale import UpscaleParams, load_realesrgan, upscale

_EXTENSIONS = {"webp": "webp", "jpeg": "jpg", "png": "png"}
_VARIANT_SUFFIX: dict[LayerLines, str] = {"keep": "", "smooth": "_smooth"}
# original_hd no tiene lienzo fijo: la pieza ocupa este margen dentro de un lienzo con su proporción.
_ORIGINAL_HD_FILL = 0.9


def process_image(
    input_path: Path,
    options: ProcessOptions,
    out_dir: Path,
    *,
    base_name: str,
    mask_override: Path | None = None,
    settings: AppSettings | None = None,
) -> ProcessResult:
    if get_settings().pipeline_mode == "stub":
        return _process_stub(input_path, options, out_dir, base_name=base_name)
    return _process_real(
        input_path,
        options,
        out_dir,
        base_name=base_name,
        mask_override=mask_override,
        settings=settings or AppSettings(),
    )


class _Timer:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        yield
        self.timings[name] = round((time.perf_counter() - started) * 1000, 1)


def _device() -> str:
    if get_settings().device == "cpu":
        return "cpu"
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        return np.asarray(ImageOps.exif_transpose(opened).convert("RGB"))


def _load_mask(path: Path, shape: tuple[int, int]) -> Alpha:
    with Image.open(path) as opened:
        mask = opened.convert("L").resize((shape[1], shape[0]), Image.Resampling.BILINEAR)
    return (np.asarray(mask, np.float32) / 255.0).astype(np.float32)


def _needed_scale(crop: Crop, presets: list[Preset], settings: AppSettings, options: ProcessOptions) -> float:
    """Cuánto hay que agrandar la pieza para el formato más exigente."""
    top, bottom, left, right = piece_bounds(crop.alpha)
    piece_w, piece_h = right - left, bottom - top
    needed = 1.0
    for preset in presets:
        spec = resolve_preset(preset, settings.export)
        if spec.width and spec.height:
            fill = options.fill_ratio or spec.default_fill_ratio
            needed = max(needed, fill * min(spec.width / piece_w, spec.height / piece_h))
        elif spec.long_side:
            needed = max(needed, spec.long_side * _ORIGINAL_HD_FILL / max(piece_w, piece_h))
    return needed


def _canvas_for(preset: Preset, crop: Crop, settings: AppSettings) -> tuple[tuple[int, int], float]:
    spec = resolve_preset(preset, settings.export)
    if spec.width and spec.height:
        return (spec.width, spec.height), 0.0
    top, bottom, left, right = piece_bounds(crop.alpha)
    long_side = spec.long_side or 3000
    ratio = (right - left) / (bottom - top)
    size = (long_side, round(long_side / ratio)) if ratio >= 1 else (round(long_side * ratio), long_side)
    return size, _ORIGINAL_HD_FILL


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _process_real(
    input_path: Path,
    options: ProcessOptions,
    out_dir: Path,
    *,
    base_name: str,
    mask_override: Path | None,
    settings: AppSettings,
) -> ProcessResult:
    timer = _Timer()
    out_dir.mkdir(parents=True, exist_ok=True)
    models_dir = get_settings().models_dir
    device = _device()
    pipeline = settings.pipeline

    with timer.stage("load"):
        rgb = _load_rgb(input_path)

    with timer.stage("segment"):
        if mask_override is not None:
            alpha = _load_mask(mask_override, rgb.shape[:2])
            components = 1
        else:
            model = load_birefnet(models_dir / "birefnet", device)
            result = segment(rgb, model, device, SegmentationParams(size=pipeline.segmentation_size))
            alpha, components = result.alpha, result.components
        mask_path = out_dir / f"{base_name}_mask.png"
        Image.fromarray(to_uint8(alpha), "L").save(mask_path)

    if not (alpha > 0.5).any():
        raise ValueError("No se encontró ninguna pieza en la imagen.")

    with timer.stage("color"):
        image: FloatImage = to_float(rgb)
        # Recortar primero: el color se calcula con la foto completa pero solo se aplica al recorte.
        raw_crop = crop_to_piece(image, alpha, padding_ratio=0.04)
        color = correct_color(image, alpha, white_balance=options.white_balance, apply_to=raw_crop.image)
        crop = Crop(decontaminate_edges(color.image, raw_crop.alpha), raw_crop.alpha)

    needed = _needed_scale(crop, options.presets, settings, options)
    reasons = review_reasons(alpha, components, settings.quality, needed_upscale=needed)

    with timer.stage("upscale"):
        factor = min(needed, float(options.upscale))
        use_model = pipeline.upscale_model == "realesrgan_x2plus" and factor > 1.05
        upscaler = (
            load_realesrgan(models_dir / "realesrgan" / "RealESRGAN_x2plus.pth", device)
            if use_model
            else None
        )
        params = UpscaleParams(
            tile_size=pipeline.tile_size,
            tile_overlap=pipeline.tile_overlap,
            detail_reinjection=pipeline.detail_reinjection,
            use_model=use_model,
        )
        up_image, up_alpha = upscale(crop.image, crop.alpha, factor, upscaler, device, params)
        crop = Crop(up_image, up_alpha)

    shadow_mode = resolve_shadow(options.shadow, crop.image, crop.alpha, ShadowParams())
    background = _hex_to_rgb(settings.export.background_hex)
    variants: list[LayerLines] = (
        ["keep", "smooth"] if options.generate_both_layer_variants else [options.layer_lines]
    )
    outputs: list[OutputFile] = []

    for variant in variants:
        with timer.stage(f"layers_{variant}"):
            variant_image = (
                smooth_layer_lines(crop.image, crop.alpha, options.smooth_strength)
                if variant == "smooth"
                else crop.image
            )
        variant_crop = Crop(variant_image, crop.alpha)
        suffix = _VARIANT_SUFFIX[variant] if len(variants) > 1 else ""
        for preset in options.presets:
            with timer.stage(f"{preset}_{variant}"):
                spec = resolve_preset(preset, settings.export)
                size, hd_fill = _canvas_for(preset, variant_crop, settings)
                fill = hd_fill or options.fill_ratio or spec.default_fill_ratio
                composed = compose_on_canvas(variant_crop, size, fill, shadow_mode, background)
                path = output_path(out_dir, base_name, preset, spec, suffix)
                data = encode(composed, spec)
                path.write_bytes(data)
                outputs.append(
                    OutputFile(
                        preset=preset,
                        path=str(path),
                        width=size[0],
                        height=size[1],
                        bytes=len(data),
                        variant=variant,
                    )
                )

    timer.timings["total"] = round(sum(timer.timings.values()), 1)
    return ProcessResult(
        outputs=outputs, mask_path=str(mask_path), review_reasons=reasons, timings_ms=timer.timings
    )


def _process_stub(
    input_path: Path, options: ProcessOptions, out_dir: Path, *, base_name: str
) -> ProcessResult:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(input_path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")

    outputs = [_render_preset(source, preset, options, out_dir, base_name) for preset in options.presets]
    return ProcessResult(outputs=outputs, timings_ms={"total": (time.perf_counter() - started) * 1000})


def _render_preset(
    source: Image.Image, preset: Preset, options: ProcessOptions, out_dir: Path, base_name: str
) -> OutputFile:
    spec = PRESETS[preset]
    fill = options.fill_ratio or spec.default_fill_ratio
    if spec.width is None or spec.height is None:
        long_side = spec.long_side or max(source.size)
        scale = long_side / max(source.size)
        canvas = source.resize(
            (round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS
        )
    else:
        canvas = Image.new("RGB", (spec.width, spec.height), "#FFFFFF")
        scale = min(spec.width * fill / source.width, spec.height * fill / source.height)
        piece = source.resize(
            (round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS
        )
        canvas.paste(piece, ((spec.width - piece.width) // 2, (spec.height - piece.height) // 2))

    suffix = "" if preset == "storefront" else f"_{preset}"
    path = out_dir / f"{base_name}{suffix}.{_EXTENSIONS[spec.format]}"
    save_kwargs: dict[str, int | bool] = {} if spec.format == "png" else {"quality": spec.quality}
    canvas.save(path, format=spec.format.upper(), **save_kwargs)
    return OutputFile(
        preset=preset,
        path=str(path),
        width=canvas.width,
        height=canvas.height,
        bytes=path.stat().st_size,
        variant=options.layer_lines,
    )
