"""Procesa una carpeta de fotos sin la web y genera una hoja de contacto HTML antes/después.

Uso:
  python -m scripts.process_folder ../samples ../data/reports/prueba
  python -m scripts.process_folder ../samples out --preset storefront --preset instagram_feed --layers both
"""

import argparse
import html
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageOps

from app.contracts import AppSettings, Preset, ProcessOptions, ProcessResult
from app.pipeline.export import slugify
from app.pipeline.run import process_image

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preset", action="append", dest="presets", choices=list(Preset.__args__))  # type: ignore[attr-defined]
    parser.add_argument("--layers", choices=["keep", "smooth", "both"], default="both")
    parser.add_argument("--smooth-strength", type=int, default=35)
    parser.add_argument("--shadow", choices=["auto", "none", "soft", "strong"], default="auto")
    parser.add_argument("--upscale", type=int, choices=[1, 2, 4], default=4)
    return parser.parse_args(argv)


def _thumbnail(source: Path, target: Path, long_side: int = 900) -> None:
    with Image.open(source) as opened:
        picture = ImageOps.exif_transpose(opened).convert("RGB")
    picture.thumbnail((long_side, long_side))
    picture.save(target, quality=85)


def _report(output: Path, rows: list[tuple[Path, str, ProcessResult | None, str | None]]) -> Path:
    cards = []
    for source, base_name, result, error in rows:
        before = f"thumbs/{base_name}.jpg"
        if result is None:
            body = f'<p class="error">{html.escape(error or "error")}</p>'
        else:
            images = "".join(
                f'<figure><img src="{html.escape(Path(o.path).name)}" loading="lazy">'
                f"<figcaption>{o.preset} · {o.variant} · {o.width}x{o.height} · {o.bytes / 1024:.0f} KB"
                "</figcaption></figure>"
                for o in result.outputs
            )
            reasons = ", ".join(result.review_reasons) or "ok"
            total = result.timings_ms.get("total", 0) / 1000
            body = (
                f'<p class="meta">{html.escape(reasons)} · {total:.1f} s</p><div class="row">{images}</div>'
            )
        cards.append(
            f'<section><h2>{html.escape(source.name)}</h2><div class="row">'
            f'<figure><img src="{before}" loading="lazy"><figcaption>original</figcaption></figure>'
            f"</div>{body}</section>"
        )
    page = output / "index.html"
    page.write_text(
        "<!doctype html><meta charset='utf-8'><title>Hoja de contacto</title><style>"
        "body{font:14px system-ui;margin:24px;background:#eee}section{background:#fff;padding:16px;"
        "margin-bottom:16px;border-radius:8px}.row{display:flex;gap:12px;flex-wrap:wrap}"
        "figure{margin:0}img{height:360px;border:1px solid #ddd;background:#fff}"
        "figcaption{font-size:12px;color:#555}.meta{color:#333}.error{color:#b00}</style>"
        "<h1>Hoja de contacto</h1>" + "".join(cards),
        encoding="utf-8",
    )
    return page


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    files = sorted(p for p in args.source.iterdir() if p.suffix.lower() in _IMAGE_SUFFIXES)
    if not files:
        print(f"No hay imágenes en {args.source}")
        return 1
    options = ProcessOptions(
        presets=args.presets or ["storefront", "instagram_feed"],
        layer_lines="smooth" if args.layers == "smooth" else "keep",
        smooth_strength=args.smooth_strength,
        shadow=args.shadow,
        upscale=args.upscale,
        generate_both_layer_variants=args.layers == "both",
    )
    (args.output / "thumbs").mkdir(parents=True, exist_ok=True)
    settings = AppSettings()
    rows: list[tuple[Path, str, ProcessResult | None, str | None]] = []
    summary = []
    for index, source in enumerate(files, start=1):
        base_name = f"{index:02d}-{slugify(source.stem)}"
        _thumbnail(source, args.output / "thumbs" / f"{base_name}.jpg")
        started = time.perf_counter()
        try:
            result = process_image(source, options, args.output, base_name=base_name, settings=settings)
        except Exception as error:  # la CLI reporta el error y sigue con la siguiente foto
            rows.append((source, base_name, None, str(error)))
            print(f"[{index}/{len(files)}] {source.name}: ERROR {error}")
            continue
        elapsed = time.perf_counter() - started
        rows.append((source, base_name, result, None))
        summary.append({"file": source.name, "seconds": round(elapsed, 2), **result.model_dump(mode="json")})
        print(
            f"[{index}/{len(files)}] {source.name}: {elapsed:.1f} s · {', '.join(result.review_reasons) or 'ok'}"  # noqa: E501
        )
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Hoja de contacto: {_report(args.output, rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
