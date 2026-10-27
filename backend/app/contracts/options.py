from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Preset = Literal["storefront", "instagram_feed", "instagram_square", "original_hd"]
LayerLines = Literal["keep", "smooth"]
ShadowMode = Literal["none", "soft", "strong", "auto"]
UpscaleFactor = Literal[1, 2, 4]

_DEFAULT_PRESETS: list[Preset] = ["storefront", "instagram_feed"]


class ProcessOptions(BaseModel):
    """Cómo se procesa una imagen. El lote fija los valores por defecto; cada imagen puede cambiarlos."""

    model_config = ConfigDict(extra="forbid")

    presets: list[Preset] = Field(default_factory=lambda: _DEFAULT_PRESETS.copy(), min_length=1)
    layer_lines: LayerLines = "keep"
    smooth_strength: int = Field(
        default=35, ge=0, le=100, description="Solo aplica con layer_lines='smooth'."
    )
    shadow: ShadowMode = "auto"
    fill_ratio: float | None = Field(
        default=None,
        ge=0.5,
        le=0.95,
        description="Fracción del lado mayor que ocupa la pieza. None = valor por defecto de cada preset.",
    )
    upscale: UpscaleFactor = 2
    white_balance: bool = True
    generate_both_layer_variants: bool = False

    @model_validator(mode="after")
    def _unique_presets(self) -> "ProcessOptions":
        self.presets = list(dict.fromkeys(self.presets))
        return self
