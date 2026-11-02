"""Fase 13: "Mejorar con IA". Un servicio en la nube rehace la foto ya compuesta por el estudio.

Se usa solo si la foto lo pide (`ProcessOptions.ai_enhance`) y el resultado se entrega como una variante
más ("ai"): la foto fiel del estudio siempre queda. La instrucción fija pide la misma pieza (forma, colores,
detalles) con luz de estudio y como fotografía real, nunca animada; Ajustes > IA puede agregarle texto.

Servicios:
- `fal_flux_kontext`: FLUX.1 Kontext de Black Forest Labs, servido por fal.ai (edición guiada por texto).
- `openai`: edición de imágenes de OpenAI (gpt-image-2; pide `input_fidelity=high` para conservar
  detalles y, si el modelo no lo admite, repite la petición sin él).
"""

import base64
import io

import cv2
import httpx
import numpy as np
from PIL import Image

from app.contracts.settings import AiSettings
from app.pipeline.types import FloatImage, to_float, to_uint8

BASE_PROMPT = (
    "Turn this into a professional e-commerce product photograph of the very same 3D-printed figurine. "
    "Keep the object exactly as it is: same shape, proportions, pose, colors, painted details and base. "
    "Do not add, remove, redesign or restyle anything on the figurine, and keep it the same size and "
    "position in the frame. Improve only the photography: soft diffuse studio lighting, no harsh glare, "
    "clean matte look, sharp focus across the whole piece, and a natural soft shadow where it rests on a "
    "light gray tabletop with a seamless light background. It must look like a real photograph: not a 3D "
    "render, not a cartoon, not an illustration, not anime, not animated."
)

_FAL_URL = "https://fal.run/{model}"
_OPENAI_URL = "https://api.openai.com/v1/images/edits"


class AiEnhanceError(Exception):
    """Falla del servicio de IA, con un mensaje para la persona (nunca incluye la clave)."""


def is_configured(settings: AiSettings) -> bool:
    if settings.provider == "fal_flux_kontext":
        return settings.fal_api_key is not None
    if settings.provider == "openai":
        return settings.openai_api_key is not None
    return False


def build_prompt(settings: AiSettings) -> str:
    extra = settings.extra_prompt.strip()
    return f"{BASE_PROMPT} {extra}" if extra else BASE_PROMPT


def enhance_with_ai(
    image: FloatImage, settings: AiSettings, client: httpx.Client | None = None
) -> FloatImage:
    """Devuelve la foto rehecha al mismo tamaño que `image` (la IA entrega ~1 MP; se ajusta sin deformar)."""
    if not is_configured(settings):
        raise AiEnhanceError(
            "Mejorar con IA no está configurado: elige el servicio y su clave en Ajustes > IA."
        )
    png = _encode_png(image)
    prompt = build_prompt(settings)
    own_client = client is None
    http = client or httpx.Client(timeout=settings.timeout_seconds)
    try:
        if settings.provider == "fal_flux_kontext":
            result = _fal(http, png, prompt, settings)
        else:
            result = _openai(http, png, prompt, settings, image.shape[1], image.shape[0])
    except httpx.TimeoutException as error:
        raise AiEnhanceError("El servicio de IA tardó demasiado en responder.") from error
    except httpx.HTTPStatusError as error:
        raise AiEnhanceError(_status_message(error.response, _secrets(settings))) from error
    except httpx.HTTPError as error:
        raise AiEnhanceError("No se pudo conectar con el servicio de IA.") from error
    except (KeyError, IndexError, TypeError, ValueError, OSError) as error:
        raise AiEnhanceError("El servicio de IA devolvió una respuesta que no se pudo leer.") from error
    finally:
        if own_client:
            http.close()
    return _fit(result, image.shape[1], image.shape[0])


def _secrets(settings: AiSettings) -> list[str]:
    keys = (settings.fal_api_key, settings.openai_api_key)
    return [key.get_secret_value() for key in keys if key is not None and key.get_secret_value()]


def _service_detail(response: httpx.Response) -> tuple[str, str]:
    """(código, mensaje) del error según lo devuelve OpenAI (`error.code/message`) o fal.ai (`detail`)."""
    try:
        body = response.json()
    except ValueError:
        return "", response.text[:200]
    if not isinstance(body, dict):
        return "", ""
    error = body.get("error")
    if isinstance(error, dict):
        return str(error.get("code") or error.get("type") or ""), str(error.get("message") or "")
    detail = body.get("detail")
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        return "", str(detail[0].get("msg") or "")
    return "", str(detail or body.get("message") or "")


def _status_message(response: httpx.Response, secrets: list[str]) -> str:
    """Mensaje en español para la persona; agrega el texto del servicio sin la clave."""
    status = response.status_code
    code, detail = _service_detail(response)
    for secret in secrets:
        detail = detail.replace(secret, "***")
    detail = " ".join(detail.split())[:300]
    if status == 401:
        text = "La clave del servicio de IA no es válida: revísala en Ajustes > IA."
    elif status == 403:
        text = (
            "El servicio de IA no permite usar este modelo con tu cuenta "
            "(en OpenAI suele faltar verificar la organización)."
        )
    elif code in {"insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached"} or (
        status in {402, 429} and any(word in detail.lower() for word in ("credit", "balance", "quota"))
    ):
        text = "La cuenta del servicio de IA no tiene saldo: recarga créditos y vuelve a procesar."
    elif status == 429:
        text = "El servicio de IA recibió demasiadas peticiones: espera un momento y vuelve a procesar."
    elif status == 404 or code == "model_not_found":
        text = "El modelo de IA elegido no existe o fue retirado: cámbialo en Ajustes > IA."
    else:
        text = f"El servicio de IA respondió con error {status}."
    return f"{text} Detalle: {detail}" if detail else text


def _encode_png(image: FloatImage) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(to_uint8(image), "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _decode(data: bytes) -> FloatImage:
    with Image.open(io.BytesIO(data)) as picture:
        return to_float(np.asarray(picture.convert("RGB")))


def _fal(http: httpx.Client, png: bytes, prompt: str, settings: AiSettings) -> FloatImage:
    assert settings.fal_api_key is not None
    data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    response = http.post(
        _FAL_URL.format(model=settings.fal_model),
        headers={"Authorization": f"Key {settings.fal_api_key.get_secret_value()}"},
        json={"prompt": prompt, "image_url": data_uri, "num_images": 1, "output_format": "png"},
    )
    response.raise_for_status()
    url = str(response.json()["images"][0]["url"])
    if url.startswith("data:"):
        return _decode(base64.b64decode(url.split(",", 1)[1]))
    download = http.get(url)
    download.raise_for_status()
    return _decode(download.content)


def _openai_size(width: int, height: int) -> str:
    ratio = width / height
    if ratio > 1.2:
        return "1536x1024"
    if ratio < 1 / 1.2:
        return "1024x1536"
    return "1024x1024"


def _openai(
    http: httpx.Client, png: bytes, prompt: str, settings: AiSettings, width: int, height: int
) -> FloatImage:
    assert settings.openai_api_key is not None
    data = {
        "model": settings.openai_model,
        "prompt": prompt,
        "size": _openai_size(width, height),
        "quality": settings.openai_quality,
        "n": "1",
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}"}
    files = {"image": ("pieza.png", png, "image/png")}
    # Conserva más fielmente los detalles de la foto de entrada; no todos los modelos lo admiten.
    response = http.post(_OPENAI_URL, headers=headers, data={**data, "input_fidelity": "high"}, files=files)
    if response.status_code == 400 and _rejects_param(response, "input_fidelity"):
        response = http.post(_OPENAI_URL, headers=headers, data=data, files=files)
    response.raise_for_status()
    return _decode(base64.b64decode(response.json()["data"][0]["b64_json"]))


def _rejects_param(response: httpx.Response, param: str) -> bool:
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return False
    return isinstance(error, dict) and (error.get("param") == param or param in str(error.get("message")))


def _fit(image: FloatImage, width: int, height: int) -> FloatImage:
    """Cubre el lienzo del formato sin deformar (recorta lo que sobre, centrado)."""
    src_h, src_w = image.shape[:2]
    scale = max(width / src_w, height / src_h)
    new_w, new_h = max(round(src_w * scale), width), max(round(src_h * scale), height)
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    resized = cv2.resize(image, (new_w, new_h), interpolation=interpolation)
    x0, y0 = (new_w - width) // 2, (new_h - height) // 2
    fitted: FloatImage = np.clip(resized[y0 : y0 + height, x0 : x0 + width], 0.0, 1.0).astype(np.float32)
    return fitted
