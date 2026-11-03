from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Preset = Literal["storefront", "instagram_feed", "instagram_square", "original_hd"]
LayerLines = Literal["keep", "smooth"]
# Variantes de salida: las dos de líneas de capa y la versión rehecha por una IA en la nube (Fase 13).
OutputVariant = Literal["keep", "smooth", "ai"]
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
    # Por defecto se suavizan: en una impresión 3D las líneas de capa se marcan mucho en la foto (Fase 12).
    layer_lines: LayerLines = "smooth"
    smooth_strength: int = Field(
        default=80, ge=0, le=100, description="Solo aplica con layer_lines='smooth'."
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
    auto_adjust: bool = Field(
        default=True,
        description=(
            "Ajuste automático según la foto: mide la nitidez, el rango de tonos y los brillos de la pieza "
            "y elige la fuerza de enfoque, realce y reducción de brillos. Con False se usan los valores de "
            "enhance, sharpen y glare."
        ),
    )
    # 80: lo más cercano a una foto de estudio sin exagerar (comparado con una foto de referencia, Fase 12).
    enhance: int = Field(
        default=80,
        ge=0,
        le=100,
        description=(
            "Realce de color tipo foto de estudio (niveles, viveza, contraste local). 0 = colores tal cual."
        ),
    )
    # 60: nitidez cercana a una foto de catálogo sin halos (medido con una foto de celular, Fase 12).
    sharpen: int = Field(
        default=60,
        ge=0,
        le=100,
        description="Enfoque final sobre la imagen compuesta. 0 = sin enfoque.",
    )
    # 80: el reflejo de la luz sobre el plástico baja sin que la pieza se vea pintada encima (Fase 12).
    glare: int = Field(
        default=80,
        ge=0,
        le=100,
        description=(
            "Reducir brillos: baja la luz que se refleja sobre las superficies de color. El blanco y el "
            "negro de pintura no se tocan. 0 = brillos tal como salieron en la foto."
        ),
    )
    # F12.16: retoque tipo catálogo calibrado contra la versión de ChatGPT del Arthas, sin IA generativa.
    finish: int = Field(
        default=50,
        ge=0,
        le=100,
        description=(
            "Acabado estudio: curva de tonos con luces que resaltan, claridad en el relieve y metales más "
            "cálidos. 0 = sin acabado. Con auto_adjust lo decide cada foto."
        ),
    )
    white_balance: bool = True
    generate_both_layer_variants: bool = False
    # Fase 13: además de la foto normal, una versión rehecha por la IA de Ajustes > IA (cuesta por imagen).
    ai_enhance: bool = Field(
        default=False,
        description=(
            "Mejorar con IA: entrega además una variante 'ai' rehecha por el servicio de Ajustes > IA "
            "(foto de producto realista, sin estilo animado). Se cobra por imagen y puede cambiar detalles."
        ),
    )
    rotate: Rotation = Field(default=0, description="Giro en grados, en sentido horario, antes de recortar.")
    crop: CropBox | None = Field(default=None, description="Recorte previo; None = foto completa.")

    @model_validator(mode="after")
    def _unique_presets(self) -> "ProcessOptions":
        self.presets = list(dict.fromkeys(self.presets))
        return self
