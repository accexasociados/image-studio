from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Preset = Literal["storefront", "instagram_feed", "instagram_square", "original_hd"]
LayerLines = Literal["keep", "smooth"]
ShadowMode = Literal["none", "soft", "strong", "auto"]
UpscaleFactor = Literal[1, 2, 4]
Rotation = Literal[0, 90, 180, 270]
# white = fondo liso de hoy; studio = piso continuo de estudio; pedestal = base redonda de exhibición;
# color = piso continuo en el color de marca; photo = una foto de fondo de la biblioteca.
SceneStyle = Literal["white", "studio", "pedestal", "color", "photo"]

_DEFAULT_PRESETS: list[Preset] = ["storefront", "instagram_feed"]


class CropBox(BaseModel):
    """Recorte en fracciones (0 a 1) de la foto ya rotada. Se elige por imagen desde la web."""

    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> "CropBox":
        if self.x + self.width > 1.0001 or self.y + self.height > 1.0001:
            raise ValueError("El recorte se sale de la foto.")
        return self


class ProcessOptions(BaseModel):
    """Cómo se procesa una imagen. El lote fija los valores por defecto; cada imagen puede cambiarlos."""

    model_config = ConfigDict(extra="forbid")

    presets: list[Preset] = Field(default_factory=lambda: _DEFAULT_PRESETS.copy(), min_length=1)
    layer_lines: LayerLines = "keep"
    smooth_strength: int = Field(
        default=35, ge=0, le=100, description="Solo aplica con layer_lines='smooth'."
    )
    shadow: ShadowMode = "auto"
    shadow_intensity: int = Field(
        default=100, ge=0, le=200, description="Porcentaje de la opacidad del modo de sombra (100 = normal)."
    )
    fill_ratio: float | None = Field(
        default=None,
        ge=0.5,
        le=0.95,
        description="Fracción del lado mayor que ocupa la pieza. None = valor por defecto de cada preset.",
    )
    upscale: UpscaleFactor = 2
    upscale_fidelity: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Al agrandar, porcentaje del detalle fino que sale de la foto original y no del modelo "
            "(100 = lo más fiel, 0 = todo lo reconstruye la IA). None = Ajustes > Proceso."
        ),
    )
    scene: SceneStyle | None = Field(
        default=None, description="Fondo de la pieza. None = Ajustes > Exportación."
    )
    background_id: str | None = Field(
        default=None,
        max_length=32,
        description="Foto de fondo con scene='photo'. None = la de Ajustes > Exportación.",
    )
    white_balance: bool = True
    generate_both_layer_variants: bool = False
    rotate: Rotation = Field(default=0, description="Giro en grados, en sentido horario, antes de recortar.")
    crop: CropBox | None = Field(default=None, description="Recorte previo; None = foto completa.")

    @model_validator(mode="after")
    def _unique_presets(self) -> "ProcessOptions":
        self.presets = list(dict.fromkeys(self.presets))
        return self
