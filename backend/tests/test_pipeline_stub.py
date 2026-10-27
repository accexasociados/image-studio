from pathlib import Path

from PIL import Image

from app.contracts import ProcessOptions
from app.pipeline.run import process_image


def test_stub_renders_every_preset_on_white(tmp_path: Path) -> None:
    source = tmp_path / "pieza.jpg"
    Image.new("RGB", (800, 600), (200, 40, 40)).save(source)

    result = process_image(
        source,
        ProcessOptions(presets=["storefront", "instagram_feed", "instagram_square"]),
        tmp_path / "out",
        base_name="DRG-01",
    )

    sizes = {output.preset: (output.width, output.height) for output in result.outputs}
    assert sizes == {
        "storefront": (2000, 2000),
        "instagram_feed": (1080, 1350),
        "instagram_square": (1080, 1080),
    }
    storefront = next(output for output in result.outputs if output.preset == "storefront")
    assert Path(storefront.path).name == "DRG-01.webp"
    assert storefront.bytes < 5 * 1024 * 1024
    with Image.open(storefront.path) as rendered:
        corner = rendered.convert("RGB").getpixel((5, 5))
    assert corner == (255, 255, 255)
