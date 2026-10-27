# Plan de ejecución — Image Studio

Herramienta local para convertir fotos de piezas de **impresión 3D** en fotos de producto con **fondo blanco**, buena resolución y acabado natural (que no parezca generado por IA), lista para el **storefront** y para **Instagram**.

Este plan lo ejecutan dos agentes en paralelo (**Claude Code** y **Codex**). Leer primero la sección *Protocolo de trabajo entre agentes*.

Fecha de creación: **2026-10-26**.

---

## Cómo usar este documento

- Cada tarea tiene casilla y dueño sugerido: `[ ]` pendiente, `[~]` en curso, `[x]` terminada.
- Al tomar una tarea, cambiar `[ ]` por `[~]` y escribir el agente al final: `[~] F2.3 … — (codex)`. Al terminarla, `[x]`.
- Una fase está **terminada** cuando todas sus tareas están en `[x]` y se cumple su *criterio de salida*.
- Actualizar la tabla de progreso al cerrar cada fase.
- Las rutas son relativas a `image-studio/`.

## Tabla de progreso

| Fase | Objetivo | Dueño sugerido | Depende de | Estado |
|---|---|---|---|---|
| 0 | Fundaciones y contratos | Claude | — | Completa (2026-10-26) |
| 1 | Proceso de imagen para impresión 3D | Claude | F0 + fotos de prueba | Código listo; falta que el usuario apruebe la hoja de contacto |
| 2 | API, cola de trabajos y worker | Codex | F0 | Completa (2026-10-27), unida a `main` |
| 3 | Interfaz web: lotes y subida en bloque | Codex | F0 (API simulada) | En progreso |
| 4 | Importar desde enlaces (Google Photos, Drive, URL directa) | Codex | F2 | Pendiente |
| 5 | Avisos (Telegram, Windows, navegador) | Codex | F2 | Pendiente |
| 6 | Galería de revisión y editor (antes/después, ajustes, pincel) | Claude | F1, F3 | Código listo (rama `feat/F6-review-gallery`); falta el lote de 100 fotos (F8) |
| 7 | Entradas extra: bot de Telegram y carpeta vigilada | Codex | F2, F5 | Pendiente |
| 8 | Validación con lote real de 100 fotos y ajuste fino | Claude + usuario | F1–F6 | Pendiente |
| 9 | Nube (opción C): Docker, Redis, S3, autenticación e integración con el ecommerce | Codex (9.1–9.7) + Claude (9.8) | F8 | Pendiente |
| 10 | Mejora de resolución: modelo elegible y fidelidad por foto | Claude (10.1–10.4) + Codex (10.5–10.7) | F1, F6 | Hecha (en `main`) |
| 11 | Escenas: la pieza apoyada en estudio, pedestal, color de marca o foto de fondo | Claude (11.1–11.5) + Codex (11.6–11.9) | F10 | Backend listo (rama `feat/F11-scenes`); falta la web |

Las fases 1, 2 y 3 pueden avanzar **en paralelo**: la Fase 0 ya dejó los contratos, la configuración y el proceso en modo `stub`.

---

## Decisiones tomadas

| Tema | Decisión |
|---|---|
| Ubicación | `e:\proyectos\accex\abc\image-studio\`, con su **propio repositorio git**, como los demás proyectos del monorepo |
| Ejecución | Local, en Windows 11 con **NVIDIA GTX 1660 (6 GB)** |
| Volumen | Lotes de unas 100 fotos; objetivo de 10 a 15 minutos por lote |
| Tipo de imagen | Piezas de impresión 3D (PLA/PETG; pueden ser blancas, de colores, translúcidas o multicolor) |
| Principio clave | La IA **solo recorta y mejora la resolución**: nunca regenera el producto. Sin modelos generativos en el proceso por defecto |
| Líneas de capa | Las dos opciones: **conservar** (por defecto) y **suavizar**. Se eligen por lote y por imagen, y la galería permite generar ambas para comparar |
| Salidas | Storefront + Instagram (ver *Formatos de salida*) |
| Alcance | **Opción C** (decidido el 2026-10-26): estudio local completo (web, subida en bloque, enlaces, galería y editor, avisos, bot de Telegram como entrada) **y preparado para la nube** (Docker, Redis, S3, autenticación) |
| Crecer después | Proceso desacoplado de las entradas: la web, Telegram y la carpeta solo **encolan trabajos**. Cola (`JobQueue`) y archivos (`Storage`) detrás de interfaces, para pasar de SQLite/disco a Redis/S3 sin reescribir |
| Configuración | **Todo configurable desde la web** (Ajustes): Telegram, avisos, formatos de salida, importadores, carpeta vigilada, modelos y umbrales de calidad, en `AppSettings` (tabla `settings`, secretos cifrados). El `.env` queda solo para arranque, igual que la regla del resto del ecosistema |

### Las dos opciones de líneas de capa

- **Conservar (por defecto):** la textura de las capas se mantiene como en la foto, solo más nítida. Es honesto con el producto (el cliente ve que es impresión 3D y lo que recibirá) y es lo que menos parece IA. Técnica: mejora 2x y luego se reinyecta el detalle fino de la imagen original (mezcla de alta frecuencia) para que el modelo no "alise" las capas.
- **Suavizar:** se atenúan las líneas solo dentro de la pieza (filtro guiado/bilateral sobre la máscara, intensidad regulable de 0 a 100). La superficie se ve más lisa y "comercial". Con intensidad alta empieza a verse plástica, así que el máximo por defecto es moderado.

---

## Stack técnico

| Capa | Tecnología | Notas |
|---|---|---|
| Backend | Python 3.11 + FastAPI + Uvicorn | `backend/` |
| Base de datos | SQLite (SQLAlchemy 2 + Alembic) | Archivo en `data/studio.db` |
| Cola | Tabla `jobs` en SQLite, consumida por un worker con concurrencia 1 (una sola GPU) | Interfaz `JobQueue` para cambiarla por Redis en la Fase 9 |
| Recorte de fondo | **BiRefNet** (`ZhengPeng7/BiRefNet`, PyTorch/transformers) a 1024 px | Respaldo opcional: RMBG-2.0 |
| Mejora de resolución | **Real-ESRGAN x2plus** cargado con `spandrel`, procesando por partes (tiles) | No usar el paquete `realesrgan` (choca con torchvision nuevo) |
| Imagen | Pillow, OpenCV, NumPy | Color, sombra, composición |
| GPU | PyTorch 2.14 con CUDA 12.6 (`cu126`), **forzando FP32** | La serie GTX 16xx da NaN o imágenes negras en FP16 |
| Configuración | `AppSettings` (Pydantic) por sección en la tabla `settings`; secretos cifrados con Fernet (`SECRET_KEY` o `data/secret.key` en local) | `app/contracts/settings.py`, `app/db/settings_store.py` |
| Archivos | Interfaz `Storage` (`app/storage/`): disco local ahora, S3 en la Fase 9 | La BD guarda claves relativas, no rutas absolutas |
| Frontend | Vite + React 19 + TypeScript + Tailwind 4 + TanStack Query + i18next | `web/`; mismo estilo que `ecommerce-dashboard` |
| Tiempo real | Server-Sent Events (SSE) para progreso del lote | |
| Avisos | Telegram Bot API, notificaciones de Windows (`win11toast`), Notification API del navegador | |
| Tests | `pytest` (backend), Vitest (web) | |

Puertos locales: API **8090**, web (Vite) **5180**, para no chocar con el resto del ecosistema (3000–3003, 5173–5175).

---

## Estructura de carpetas (objetivo)

```
image-studio/
├── AGENTS.md                  # Reglas para agentes (Claude/Codex)
├── PLAN_EJECUCION.md          # Este documento
├── README.md
├── .env.example               # Solo arranque: puertos, rutas, dispositivo
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py            # FastAPI
│   │   ├── config.py          # Solo arranque (.env)
│   │   ├── gpu.py             # Detección de GPU (no falla sin torch)
│   │   ├── contracts/         # Esquemas Pydantic compartidos (FUENTE DE VERDAD), incl. settings.py
│   │   ├── db/                # Modelos SQLAlchemy, sesión, migrate.py, settings_store.py
│   │   ├── storage/           # Storage: local.py (ahora), s3.py (Fase 9)
│   │   ├── api/               # Routers: batches, images, imports, settings, events
│   │   ├── queue/             # JobQueue (SQLite) + worker
│   │   ├── pipeline/          # Proceso de imagen (sin FastAPI ni BD)
│   │   │   ├── segment.py     # BiRefNet + refinado de bordes
│   │   │   ├── upscale.py     # Real-ESRGAN + reinyección de detalle
│   │   │   ├── color.py       # Balance de blancos, exposición
│   │   │   ├── layers.py      # Conservar / suavizar líneas de capa
│   │   │   ├── shadow.py      # Sombra de contacto
│   │   │   ├── compose.py     # Lienzo blanco, encuadre, márgenes
│   │   │   ├── export.py      # Formatos y presets de salida
│   │   │   ├── quality.py     # Detección de casos dudosos
│   │   │   └── run.py         # process_image(input, options) -> outputs
│   │   ├── importers/         # google_photos.py, google_drive.py, direct_url.py
│   │   ├── notifiers/         # telegram.py, windows.py
│   │   └── inputs/            # telegram_bot.py, hot_folder.py
│   ├── scripts/
│   │   ├── check_gpu.py
│   │   ├── download_models.py
│   │   └── process_folder.py  # CLI: procesar una carpeta sin la web
│   └── tests/
├── web/                       # Vite + React
├── data/                      # (gitignored) BD, originales, máscaras, salidas
├── models/                    # (gitignored) pesos descargados
└── samples/                   # (gitignored) fotos de prueba del usuario
```

---

## Formatos de salida

Basados en el código actual del ecosistema:

- El storefront muestra las fotos con `object-fit: contain` (`ecommerce-storefront/src/components/product/product-card.module.css`), así que el cuadrado es seguro.
- `ecommerce-api` acepta imágenes de **hasta 5 MB** y ya tiene **importación masiva de imágenes por nombre de archivo** (`ecommerce-api/src/modules/catalog/application/product-image-bulk.service.ts`): busca por SKU de variante, luego por SKU de producto y luego por slug, con sufijos `_2`, `_3` para el orden.
- Instagram por API exige **JPEG** y proporción de **4:5 a 1.91:1** (`PLAN_PUBLICACION_REDES_ECOMMERCE.md`).

| Preset | Tamaño | Formato | Uso |
|---|---|---|---|
| `storefront` | 2000×2000 (1:1) | WebP calidad 90, y JPEG opcional; siempre < 5 MB | Ficha de producto y catálogo |
| `instagram_feed` | 1080×1350 (4:5) | JPEG calidad 92, sRGB | Publicación del feed (la proporción más alta permitida) |
| `instagram_square` | 1080×1080 (1:1) | JPEG calidad 92, sRGB | Carrusel o feed cuadrado |
| `original_hd` | Lado largo de 3000 px, sin recorte de lienzo | PNG | Archivo maestro para futuros formatos |

**Nombres de archivo:** si la imagen tiene SKU, se exporta como `SKU.webp`, `SKU_2.webp`, etc. Así el `.zip` del storefront se sube directo en el importador masivo del `ecommerce-dashboard` y cada foto queda en su producto. Sin SKU, se usa el nombre del producto convertido a slug.

**Encuadre:** la pieza ocupa por defecto el 82 % del lado mayor en `storefront` y el 75 % en Instagram, centrada en lo visual (por el centro de masa de la máscara, no por el rectángulo que la contiene). La sombra queda dentro del margen.

---

## Contratos (se fijan en la Fase 0; cambiarlos exige aviso en el plan)

Estos esquemas viven en `backend/app/contracts/` y son la fuente de verdad. El frontend genera sus tipos desde el OpenAPI de FastAPI (`openapi-typescript`) y **no los escribe a mano**.

```text
ProcessOptions
  presets: list["storefront" | "instagram_feed" | "instagram_square" | "original_hd"]
  layer_lines: "keep" | "smooth"         # por defecto "keep"
  smooth_strength: int 0..100            # solo si layer_lines = smooth; por defecto 35
  shadow: "none" | "soft" | "strong" | "auto"   # auto = strong si la pieza es clara
  fill_ratio: float 0.5..0.95            # por defecto según preset
  upscale: 1 | 2 | 4                     # por defecto 2
  white_balance: bool                    # por defecto true
  generate_both_layer_variants: bool     # por defecto false

Batch
  id, name, status ("draft" | "queued" | "processing" | "done" | "failed" | "cancelled"),
  default_options: ProcessOptions, created_at, finished_at,
  counts: { total, done, review, failed }

ImageItem
  id, batch_id, source ("upload" | "google_photos" | "google_drive" | "url" | "telegram" | "hot_folder"),
  source_ref, original_path, product_name, sku,
  options_override: ProcessOptions | null,
  status ("pending" | "processing" | "done" | "review" | "failed" | "approved"),
  review_reasons: list[str], outputs: list[OutputFile], error, mask_path

OutputFile
  preset, path, width, height, bytes, variant ("keep" | "smooth")

Job
  id, image_id, kind ("process" | "reprocess" | "import"), status, attempts, created_at, started_at, finished_at

Event (SSE /api/v1/events)
  type ("batch.progress" | "image.updated" | "batch.finished" | "import.progress"), payload

AppSettings (configurable desde la web; una fila por sección en la tabla `settings`)
  general              idioma, public_base_url (para los enlaces de los avisos)
  processing_defaults  ProcessOptions por defecto de los lotes nuevos
  export               ajustes por preset (tamaño, formato, calidad, margen, peso máximo), color de fondo,
                       estrategia de nombres (sku_then_slug | slug | original)
  telegram             enabled, bot_token (secreto), allowed_chat_ids, notify_chat_ids, avisos de inicio,
                       progreso (cada N %) y fin, input_bot_enabled, send_results_as (files | zip)
  notifications        windows_toast, browser
  hot_folder           enabled, inbox_dir, outbox_dir, poll_seconds
  importers            google_drive_api_key (secreto), max_download_mb, max_images_per_import
  quality              umbrales para marcar "para revisar"
  pipeline             modelo de recorte y su tamaño, modelo de mejora, tiles, half_precision (false),
                       detail_reinjection
```

Interfaz del proceso (sin dependencias de FastAPI ni de la BD, para poder llamarlo desde cualquier entrada):

```python
def process_image(input_path: Path, options: ProcessOptions, out_dir: Path, *,
                  base_name: str, mask_override: Path | None = None) -> ProcessResult: ...
# ProcessResult: outputs: list[OutputFile], mask_path, review_reasons: list[str], timings_ms: dict
```

Interfaces para crecer a la nube (ya definidas en la Fase 0):

- `app/queue/base.py::JobQueue`: `enqueue`, `claim_next`, `complete`, `fail`, `cancel_batch`, `recover_stale`.
- `app/storage/base.py::Storage`: `save_bytes`, `read_bytes`, `exists`, `delete`, `local_path`, `public_url`. Implementada: `LocalStorage` (`DATA_DIR/files`).
- `app/db/settings_store.py`: `load_settings(session)` / `save_settings(session, settings)`, con cifrado de `SECRET_FIELDS`.

---

## Protocolo de trabajo entre agentes (Claude Code + Codex)

1. **Leer `image-studio/AGENTS.md` y este plan** antes de empezar cualquier tarea.
2. **Tomar una sola tarea a la vez** y marcarla `[~] … — (claude)` o `[~] … — (codex)` antes de tocar código. No tomar una tarea ya marcada por el otro agente.
3. **Rama por tarea:** `feat/F2.3-cola-sqlite`. Commits convencionales (`feat:`, `fix:`, `test:`…). No hacer push ni merge a `main` sin que el usuario lo pida.
4. **Propiedad de carpetas por fase** (para no pisarse):
   - Fase 1 → `backend/app/pipeline/`, `backend/scripts/process_folder.py`
   - Fase 2 → `backend/app/api/`, `backend/app/queue/`, `backend/app/db/`
   - Fase 3 y 6 → `web/`
   - Fase 4 → `backend/app/importers/`
   - Fase 5 → `backend/app/notifiers/`
   - Fase 7 → `backend/app/inputs/`
   - `backend/app/contracts/` → solo se modifica con una nota en *Registro de cambios de contrato* (al final), y el otro agente debe revisarla.
5. **Mientras el proceso real no exista**, la Fase 2 usa `pipeline/run.py` en **modo stub** (pega la imagen sobre blanco en cada preset, sin IA), activable con `PIPELINE_MODE=stub`. Ya está implementado y probado desde la Fase 0. Así la API y la web avanzan sin GPU.
8. **Configuración:** cualquier ajuste nuevo va a `AppSettings` (y a la pantalla de Ajustes), no a `.env` ni a constantes. Solo lo de arranque va a `.env.example`.
9. **Carpetas separadas por agente:** Codex trabaja en `image-studio/` y Claude en el worktree `../image-studio-claude/` (mismo repositorio, rama `feat/F1-pipeline`). Así ningún cambio de rama le mueve archivos al otro. Este plan se edita siempre en `image-studio/`. Al cerrar la fase, Claude junta su rama en `main` y borra el worktree (`git worktree remove ../image-studio-claude`).
6. **Cada tarea termina con:** tests pasando (`pytest` / `npm run test`), lint (`ruff check`, `npm run lint`), typecheck (`mypy app` / `npm run build`) y su casilla en `[x]`.
7. **Si algo del plan no cuadra con la realidad**, escribirlo en *Notas y bloqueos* y no improvisar un cambio de diseño grande.

---

## Fase 0 — Fundaciones y contratos (Claude)

Bloquea todo lo demás. Debe quedar corta.

- [x] F0.0 Python 3.11.9 instalado (winget) y GPU verificada con `nvidia-smi` (GTX 1660, 6 GB, driver 610.88). **Usar siempre `py -3.11`** para crear el entorno (`py -3.11 -m venv .venv`) y luego el `python` del venv: el `python` suelto del sistema todavía abre el alias de la Microsoft Store.
- [x] F0.1 `git init` en `image-studio/`, `.gitignore` (`data/`, `models/`, `samples/`, `.venv/`, `node_modules/`, `.env`), README con instalación. — (claude)
- [x] F0.2 `image-studio/AGENTS.md` con stack, comandos, arquitectura, regla de configuración y convenciones. El `AGENTS.md` raíz lista `image-studio/`. — (claude)
- [x] F0.3 `backend/pyproject.toml` con extras `ml` (torch, transformers, spandrel…) y `dev` (pytest, ruff, mypy estricto). torch 2.14.1+cu126 instalado y funcionando. — (claude)
- [x] F0.4 `scripts/check_gpu.py`: GTX 1660, 6143 MB, compute 7.5, FP32 OK (~45 ms por convolución de 1024×1024). — (claude)
- [x] F0.5 `scripts/download_models.py`: Real-ESRGAN x2plus con SHA-256 verificado y BiRefNet con revisión fijada (`e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4`) en `models/manifest.json`. — (claude)
- [x] F0.6 `backend/app/contracts/`: `ProcessOptions`, presets, `Batch`, `ImageItem`, `OutputFile`, `Job`, `Event`, `ProcessResult`, `Health` y **`AppSettings`** (toda la configuración editable, con secretos). — (claude)
- [x] F0.7 Modelos SQLAlchemy + migración `0001_initial_schema` (`batches`, `images`, `outputs` con versiones, `jobs`, `settings`). SQLite en WAL. La API migra sola al arrancar. — (claude)
- [x] F0.8 FastAPI en 8090 con `/api/v1/health` (incluye GPU y modo), OpenAPI en `/api/v1/openapi.json` y Swagger en `/docs`. — (claude)
- [x] F0.9 `web/` (Vite 8 + React 19 + TS 6 + Tailwind 4 + TanStack Query + i18next es/en) en 5180 con proxy y `npm run gen:api`. Pantalla de estado del sistema verificada en el navegador. — (claude)
- [x] F0.10 `.env.example` solo con arranque (incluye `SECRET_KEY`, `DATABASE_URL`, cola, almacenamiento y CORS para la nube). — (claude)
- [x] F0.11 (extra, por la opción C) Interfaces `JobQueue` y `Storage` + `LocalStorage`, `settings_store` con cifrado Fernet y proceso en modo `stub` con test. — (claude)

**Criterio de salida:** cumplido el 2026-10-26. `check_gpu.py` reconoce la GPU, `/api/v1/health` responde, la web muestra el estado, backend con 14 tests + ruff + mypy estricto en verde y web con build + lint + 2 tests en verde.

---

## Fase 1 — Proceso de imagen para impresión 3D (Claude)

**Requiere las fotos de prueba** (ver *Qué necesitamos del usuario*).

- [x] F1.1 `segment.py`: BiRefNet a 1024 px en FP32, máscara escalada al tamaño original con refinado de bordes (guided filter) y bordes suaves de 1 a 2 px. Cerrar huecos pequeños y conservar agujeros reales de la pieza. — (claude). Código de BiRefNet copiado y verificado por firma (`app/pipeline/vendor/birefnet/`). Muestra 3000×4000: 2,7 s y 3,2 GB de VRAM.
- [x] F1.2 `color.py`: balance de blancos con referencia en el fondo original (que suele ser neutro) y corrección suave de exposición y contraste, solo dentro de la máscara. Nada de saturación agresiva. — (claude). Balance de blancos calculado sobre la foto reducida (la mitad clara del fondo), sin aplicar si el fondo tiene color; exposición con tope 1,35.
- [x] F1.3 `upscale.py`: Real-ESRGAN x2 por tiles (512 px, solape de 32) en FP32; x4 opcional. **Reinyección de detalle:** mezclar la alta frecuencia de la original (escalada con Lanczos) para conservar las líneas de capa y evitar el aspecto "encerado". — (claude). Solo agranda lo necesario para el formato más exigente; una pasada x2 + Lanczos hasta 2,8x; reinyección de detalle 0,6.
- [x] F1.4 `layers.py`: modo `keep` (no tocar) y modo `smooth` (filtro guiado o bilateral solo en la pieza, con intensidad 0–100 y bordes protegidos). — (claude). Filtro guiado por canal con peso solo en el interior de la pieza.
- [x] F1.5 `shadow.py`: sombra de contacto realista (elipse difusa bajo la base, deducida de la parte inferior de la máscara) más una sombra ambiental muy tenue. El modo `auto` usa `strong` si la luminancia media de la pieza es alta (piezas blancas o claras). — (claude). Contacto + ambiental; `auto` = strong si la luminancia media de la pieza > 0,62.
- [x] F1.6 `compose.py`: lienzo `#FFFFFF` puro, centrado por centro de masa, `fill_ratio` según preset y fondo exactamente blanco fuera de la sombra (sin grises residuales). — (claude). Incluye limpieza del halo del fondo en los bordes (decontaminación) y fondo exacto verificado por test.
- [x] F1.7 `export.py`: los cuatro presets, perfil sRGB, límite de 5 MB para storefront (bajar la calidad hasta cumplirlo) y nombres por SKU o slug. — (claude). Perfil sRGB embebido; ajustes de Ajustes > Formatos aplicados con `resolve_preset`.
- [x] F1.8 `quality.py`: marcar para revisión si la máscara toca el borde de la foto, si la pieza ocupa menos del 5 % o más del 95 %, si hay varias piezas separadas, si los bordes son de baja confianza (translúcidos) o si hay poca diferencia entre la pieza y el fondo. — (claude). Códigos: touches_border, object_too_small, object_too_large, multiple_objects, uncertain_edges, low_resolution. Umbral de bordes recalibrado a 0,6.
- [x] F1.9 `run.py`: modo `real` encadenando las etapas, con tiempos por etapa en `timings_ms`. Las opciones de `AppSettings.pipeline`, `export` y `quality` se reciben como parámetro (sin leer la BD dentro del proceso). El modo `stub` ya existe desde la Fase 0. — (claude). `process_image(..., settings=AppSettings)`; carga de modelos cacheada; tiempos por etapa.
- [x] F1.10 `scripts/process_folder.py`: CLI `python -m scripts.process_folder samples/ out/ --preset storefront --layers keep` para probar sin web. — (claude). Genera además `index.html` (hoja de contacto) y `summary.json`.
- [x] F1.11 Tests con imágenes sintéticas (fondo plano más figura) y prueba de regresión visual básica (fondo blanco puro, pieza centrada, tamaño correcto, < 5 MB). — (claude). 26 tests (incluye proceso real completo sin GPU con máscara dada y Lanczos).
- [~] F1.12 Ajuste con las fotos reales: hoja de contacto HTML antes/después en `data/reports/` para que el usuario apruebe el estilo. — (claude). Generada en `image-studio-claude/data/reports/f1-final/index.html` con las 12 fotos; **falta la aprobación del usuario**.

**Criterio de salida:** con las fotos de prueba, el usuario aprueba la hoja de contacto. Menos de 10 s por imagen en la GTX 1660 con `storefront` + `instagram_feed`. Fondo `#FFFFFF` verificado por test.

---

## Fase 2 — API, cola de trabajos y worker (Codex)

Puede empezar con `PIPELINE_MODE=stub`.

- [x] F2.1 Routers `batches`: crear, listar, ver, cancelar, reintentar fallidas y cambiar `default_options`. — (codex)
- [x] F2.2 Router `images`: subida múltiple (`multipart`, hasta 200 archivos) y `.zip` (descomprimir con límites de tamaño y validar tipo real del archivo). Editar `product_name`, `sku` y `options_override`. Aprobar. — (codex)
- [x] F2.3 Importar metadatos por CSV (`archivo,nombre,sku`) para asociar nombre y SKU en bloque. — (codex)
- [x] F2.4 `queue/`: interfaz `JobQueue` + implementación SQLite (tomar trabajo con bloqueo, reintentos x2 y recuperación de trabajos que quedaron "processing" tras un reinicio). — (codex)
- [x] F2.5 Worker como proceso aparte (`python -m app.queue.worker`) con concurrencia 1. Carga los modelos una sola vez y libera VRAM si hay error de memoria (reintento con tiles más pequeños). — (codex)
- [x] F2.6 Reprocesar una imagen con otras opciones o con máscara editada (`kind=reprocess`), conservando versiones anteriores. — (codex)
- [x] F2.7 SSE `/api/v1/events` con progreso por lote e imagen. — (codex)
- [x] F2.8 Descarga `.zip` por lote y por preset (solo aprobadas, o todas), con nombres por SKU. — (codex)
- [x] F2.9 Router `settings` sobre `settings_store`: `GET /settings` (secretos enmascarados como `{configured: true}`), `PUT /settings/{section}` por sección (un secreto vacío u omitido conserva el actual; `null` explícito lo borra) y `POST /settings/telegram/test`. Cubre **todas** las secciones de `AppSettings`. — (codex)
- [x] F2.10 Tests de API (`httpx` + BD temporal) y del worker con el stub. — (codex)
- [x] F2.11 Script `scripts/dev.ps1` que levanta API + worker + web. — (codex)

### Correcciones tras la revisión del 2026-10-27 (claude)

La revisión de F2.1–F2.11 y F3.1 (commits `bd12dd5..34be4be`) pasó pytest (57), ruff, mypy, lint, test y build de la web, y cumple el criterio de salida en el caso normal (100 imágenes en `.zip` con el worker en modo stub). Antes de unir a `main` hay que corregir:

- [x] F2.12 Cancelar un lote mientras el worker procesa una imagen lo deja en `processing` para siempre: `_refresh_batch_status` (`queue/worker.py` ~315) sobrescribe `cancelled`. Un lote cancelado nunca debe volver a `queued` ni a `processing`. — (codex)
- [x] F2.13 El worker puede deshacer una cancelación: el `ValueError` de lote cancelado se trata como reintentable, el trabajo vuelve a la cola y `_record_failure` pone el lote en `queued` (`worker.py` ~106-110, ~178, ~297). Debe ser terminal y sin reintento. — (codex)
- [x] F2.14 Una sola imagen fallida marca todo el lote `failed` (`worker.py` ~297-301) sin pasar por `_refresh_batch_status`. El estado del lote debe salir de los conteos (p. ej. `done` con `failed > 0`), y `batch.finished` debe informar el estado correcto. — (codex)
- [x] F2.15 `recover_stale` (`queue/sqlite.py` ~103-112) vuelve a encolar sin tope: un trabajo que tumba el worker (CUDA, OOM) se repite en cada arranque. Contar el intento al recuperar, marcar `failed` al superar el máximo y no robar trabajos de otro worker vivo (por ejemplo, con `worker_id` + latido). — (codex)
- [x] F2.16 SSE: sin `Last-Event-ID` se repite todo el historial y la tabla `events` crece sin límite (`api/events.py` ~153). Empezar en el último evento (o aceptar `?since=`), podar eventos viejos y no bloquear el event loop con la consulta síncrona (`run_in_threadpool`). — (codex). Verificado por claude el 2026-10-27 en `7fd4001`.
- [x] F2.17 `ImageItem.outputs` mezcla todas las versiones (`api/images.py` ~56): devolver solo la última versión (o agregar `version` al contrato, con nota en el registro). — (codex). Verificado por claude el 2026-10-27 en `7fd4001`.
- [x] F2.18 En el `.zip`, las imágenes sin SKU ni nombre salen con el UUID (`api/downloads.py` ~57). Usar `source_ref` (nombre original) y respetar `AppSettings.export.filename_strategy`. Con las dos variantes de capa, usar `SKU.webp` + `SKU_smooth.webp` (ver el registro de contratos), no `SKU_keep`. — (codex). Verificado por claude el 2026-10-27 en `7fd4001`.
- [x] F2.19 Las subidas, reintentos, reprocesos y cancelaciones escriben `JobRow` directamente (`images.py` ~247, ~329; `batches.py` ~92-96, ~116) en vez de usar `JobQueue`; eso rompe el cambio a Redis de la Fase 9. — (codex). Verificado por claude el 2026-10-27 en `7fd4001`.
- [x] F2.20 Menores: un archivo que no es imagen dentro del `.zip` (p. ej. `metadata.csv`) rechaza todo el `.zip` (ignorarlo o tratarlo como CSV); falta la ruta `GET /api/v1/files/{key}` que usa `Storage.public_url` (la necesitan F3.5 y F6); `PUT /settings/{section}` recibe `dict` y el OpenAPI queda sin tipos; la API y el worker corren las migraciones al mismo tiempo en una BD nueva; clave sin uso `app.subtitle`. — (codex). Verificado por claude el 2026-10-27 en `7fd4001`.

**Integración (2026-10-27, claude):** `main` = `b7f0486`: Fase 0 + Fase 1 (`feat/F1-pipeline`) + Fase 2 y F3.1 de codex (hasta `7fd4001`) + worker conectado al proceso real (`PipelineProcessor` pasa `settings`). Probado de punta a punta con 3 fotos reales en la GPU: lote `done`, `.zip` de storefront e Instagram con nombres por SKU y `_smooth`. 72 tests, ruff y mypy en verde. Pendiente menor: `GET /files/{key}` con una clave fuera del almacenamiento responde 500 en lugar de 404. **Codex: seguir la Fase 3 desde `main`** (`git switch main` y una rama nueva por tarea).

**Criterio de salida:** subir 100 imágenes en `.zip` crea un lote, el worker las procesa (stub o real), el progreso llega por SSE y el `.zip` de salida se descarga con nombres correctos.

---

## Fase 3 — Interfaz web: lotes y subida en bloque (Codex)

Todo texto visible en **español e inglés** (i18next), sin textos fijos en el código.

- [x] F3.1 Layout base, selector de idioma, tema claro/oscuro y lista de lotes con estado y contadores. — (codex)
- [x] F3.2 Crear lote: nombre, opciones por defecto (presets, líneas de capa, sombra) y zona de arrastrar y soltar para fotos o `.zip`, con progreso de subida. (Codex, 2026-10-27) Corregido por claude el 2026-10-27: el nombre iba dentro de `default_options` (422 siempre), faltaban suavizado, margen y ambas variantes, y ahora parte de `processing_defaults` de Ajustes. Probado en el navegador.
- [ ] F3.3 Pestaña "Desde enlace" en el mismo formulario (se conecta en la Fase 4).
- [x] F3.4 Tabla editable de nombre y SKU por imagen, más carga de CSV. — (codex, 2026-10-27)
- [x] F3.5 Vista del lote en proceso: barra de progreso en vivo (SSE), miniaturas que cambian de estado y filtros (todas, listas, para revisar, fallidas). — (codex, 2026-10-27)
- [x] F3.6 Pantalla de **Ajustes** con una pestaña por sección de `AppSettings`: General, Procesamiento por defecto, Formatos de salida, Telegram (con botón "Probar"), Avisos, Carpeta vigilada, Importadores, Calidad y Modelos. Los secretos se muestran como "Configurado" y se reemplazan sin revelarse. — (codex, 2026-10-27)
- [x] F3.7 Tests de componentes con Vitest + Testing Library. — (codex, 2026-10-27)

**Criterio de salida:** flujo completo desde la web: crear lote → subir → ver el progreso → descargar el `.zip`.

**Aviso para codex (2026-10-27, claude):** la rama `feat/F3.2-create-batch-upload` no partió de `main` y reconstruyó a mano la Fase 1 (commits `ebe7530` y `702dd6b`). Eso borraba `.gitattributes` y `tests/test_segment.py`, devolvía `low_confidence_edge_ratio` a 0.15, quitaba `settings=` en `PipelineProcessor` y las exclusiones de `vendor` en `pyproject.toml`. En `main` solo entró `dd67a78` (F3.2) más la corrección. **No uses esa rama.** Para cada tarea: `git switch main && git pull --ff-only` (o `git reset --hard origin/main` si tu `main` local difiere) y `git switch -c feat/F3.x-...`. Nunca copies archivos de otra rama a mano: si te falta algo, haz `merge` o `rebase` sobre `main`. Antes de entregar una tarea de la web, pruébala contra la API real (crear lote, subir), no solo con `tsc` y lint. Formatea con `npm run format`.

---

## Fase 4 — Importar desde enlaces (Codex)

- [ ] F4.1 `direct_url.py`: descarga de una URL de imagen con validación de tipo, límite de tamaño y bloqueo de IPs privadas.
- [ ] F4.2 `google_photos.py`: seguir la redirección de `photos.app.goo.gl/...`, extraer del HTML del álbum compartido las URLs `lh3.googleusercontent.com` y descargarlas en resolución original (sufijo `=d`). Quitar duplicados. **No hay API oficial para álbumes compartidos**: dejar el lector aislado y con test de contrato sobre un HTML guardado, para ajustarlo fácil si Google cambia la página.
- [ ] F4.3 `google_drive.py`: carpeta o archivo público de Drive. Para carpetas, usar la API de Drive con una API key guardada en `settings` (`gdown` limita las carpetas a 50 archivos).
- [ ] F4.4 Endpoint `POST /api/v1/batches/{id}/imports` con `{ url }`: detecta el tipo de enlace, crea un trabajo `import` y reporta progreso por SSE.
- [ ] F4.5 Conexión con la pestaña "Desde enlace" de la web.
- [ ] F4.6 Tests con respuestas simuladas.

**Criterio de salida:** pegar un enlace de álbum de Google Photos de unas 100 fotos crea el lote con todas las imágenes en resolución original.

### Correcciones tras la revisión del 2026-10-27 (claude, sobre `733e908`)

Pasan los 91 tests, pero **mypy falla con 7 errores**, `ruff format` falla en `tests/test_telegram_notifier.py` y ningún test ejecuta una importación a través del worker. Probado a mano:

- [x] F4.7 **(bloqueante)** Toda importación falla: `Worker._process_import` usa `job.payload`, pero el contrato `Job` no tiene `payload` (`AttributeError`). Además `_record_failure` no toca el lote cuando `job.image_id` es `None`, así que el lote queda en `queued` para siempre. Agregar `payload` a `Job` (con nota en el registro de contrato), marcar el lote como `failed` con el mensaje del error y publicar un evento. Test que pase por el worker con la descarga simulada. — (codex, 2026-10-27)
- [x] F4.8 Google Photos con el álbum real (`photos.app.goo.gl/U6S7WECz2sseLrdK7`) devuelve 6 URLs: la portada con `=w600-h315-p-k=d` (responde 400) y avatares (`/a/…`, `/ogw/…`). Aceptar solo `/pw/`, reemplazar el parámetro de tamaño existente por `=d` en vez de añadirlo, y resolver que la página inicial solo trae una foto (el resto llega por `batchexecute`). Guardar ese HTML real como fixture del test de contrato. Si no se logra, decirlo en la web en vez de importar solo la portada. — (codex, 2026-10-27)
- [x] F4.9 SSRF: el tipo de enlace se detecta con subcadenas (`"photos.app.goo.gl" in url`), así que `http://127.0.0.1:8090/?photos.app.goo.gl` pasa, y el cliente del álbum sigue redirecciones sin validar el host. El cliente de Drive (`follow_redirects=True`) se pasa a `download_image` y se salta su validación de cada salto. Comparar el `hostname` exacto y validar cada redirección en todos los importadores. — (codex, 2026-10-27)
- [x] F4.10 Usar `settings.importers.max_download_mb` (no 40 MB fijo) y el mismo validador de las subidas (bomba de descompresión, formatos). En `_process_import` la variable `key` es la API key (`SecretStr`) y luego la clave de almacenamiento: renombrar. — (codex, 2026-10-27)
- [x] F4.11 Si la importación falla a la mitad, los archivos ya guardados quedan huérfanos y no se crea ninguna fila: confirmar por imagen o limpiar lo guardado. — (codex, 2026-10-27)

---

## Fase 5 — Avisos (Codex)

- [x] F5.1 `telegram.py`: mensajes de "lote iniciado", progreso cada 25 % y "lote terminado: X listas, Y para revisar, Z fallidas", con el enlace local a la galería. Botón "Probar" en ajustes. — (codex, 2026-10-27)
- [x] F5.2 `windows.py`: notificación nativa de Windows al terminar un lote. — (codex, 2026-10-27)
- [x] F5.3 Notificación del navegador al terminar (pidiendo permiso), con la pestaña en segundo plano. — (codex, 2026-10-27)
- [x] F5.4 Suscripción a eventos del worker (sin acoplar los notificadores al proceso de imagen). — (codex, 2026-10-27)

**Criterio de salida:** al terminar un lote llegan el mensaje de Telegram y la notificación de Windows.

### Correcciones tras la revisión del 2026-10-27 (claude, sobre `733e908`)

- [x] F5.5 Telegram manda el `id` del lote y el `dict` crudo de conteos (`{'total': 3, ...}`). Usar el nombre del lote y "X listas, Y para revisar, Z fallidas" más el enlace a la galería (`general.public_base_url`), como dice F5.1. El progreso cuenta `done` sin `review`, así que nunca llega al 100 % si alguna queda para revisar. — (codex, 2026-10-27)
- [x] F5.6 `win11toast` no está en las dependencias: la notificación de Windows nunca aparece y solo queda un log. Agregarlo a un extra opcional (`notify`) y documentarlo en el README, o usar otra vía sin dependencia. Tipar `settings_loader` (mypy). — (codex, 2026-10-27)
- [x] F5.7 Navegador: `BatchDetailPanel` abre un segundo `EventSource` que vuelve a pedir la lista en cada evento (`useBatchImages` ya escucha y agrupa), avisa al terminar **cualquier** lote (no filtra `batch_id`) y pide el permiso dentro de un evento SSE, cosa que Chrome rechaza sin un clic del usuario. Pedir el permiso con un botón y mover el aviso a un hook global para que funcione aunque el detalle del lote no esté abierto. — (codex, 2026-10-27)
- [x] F5.8 Antes de marcar `[x]`: `ruff check`, `ruff format --check`, `mypy app`, `tsc -b`, `eslint` y una prueba real (importar un enlace y terminar un lote con el worker corriendo). — (codex, 2026-10-27)

**Revisión de F4.7–F5.8 (2026-10-27, claude, rama `review/F4-F5-fixes2`).** Checks y prueba real en verde tras estas correcciones: (1) los nombres sacados de las URL de Google (tokens de ~200 caracteres) hacían que la ruta de salida superara los 260 caracteres de Windows y la foto fallaba; ahora las fotos del álbum se llaman `google-photos-001.jpg…` y cualquier nombre de URL se corta a 60 caracteres; (2) todas las fotos de una importación quedaban con la misma `position`; (3) sin clave de API, Drive responde 403 (no 404) y todo enlace público fallaba: ahora el archivo se baja directo y una carpeta pide la clave; se aceptan enlaces `/drive/folders/`; (4) F5.7 seguía a medias: `BatchDetailPanel` mantenía su `EventSource` y pedía permiso dentro del evento (aviso doble); se quitó y el texto del aviso global pasó a i18n; (5) faltaban en las traducciones `batches.source.*`, `linkLabel` y `linkPlaceholder` (la pestaña mostraba las claves); (6) Telegram (progreso) y el aviso de Windows usaban el id del lote o el `dict` crudo de conteos. El álbum de prueba tiene una sola foto (token de paginación vacío), así que no hace falta `batchexecute` para él.

---

## Fase 6 — Galería de revisión y editor (Claude)

- [x] F6.1 Galería del lote con cuadrícula, filtros y selección múltiple (aprobar o reprocesar en bloque).
- [x] F6.2 Comparador antes/después con deslizador y zoom al 100 % para revisar bordes y líneas de capa.
- [x] F6.3 Panel de ajustes por imagen (líneas de capa e intensidad, sombra, margen, presets) que reprocesa y muestra el resultado.
- [x] F6.4 Generar ambas variantes de líneas de capa y elegir una.
- [x] F6.5 Recortar o rotar el original antes de procesar.
- [x] F6.6 **Pincel de máscara** (sumar o borrar, con tamaño y dureza regulables, deshacer y rehacer) sobre canvas. Guarda la máscara y reprocesa con `mask_override`.
- [x] F6.7 Atajos de teclado para revisar rápido (A aprobar, R reprocesar, ←/→ navegar).
- [x] F6.8 Exportar las aprobadas por preset.

**Criterio de salida:** se puede revisar un lote de 100 fotos, corregir una pieza translúcida con el pincel y exportar solo las aprobadas.

**Estado (2026-10-27, claude):** rama `feat/F6-review-gallery` (sobre `feat/F3.7-component-tests` de codex). Probado en el navegador con 3 fotos reales en la GPU: galería con miniaturas, selección y aprobación en bloque, visor con comparador y zoom al 100 %, ajustes por foto, elección de variante, giro y recorte, pincel (borrar, deshacer, rehacer, guardar y reprocesar) y descarga del `.zip` con la variante elegida. Falta validarlo con el lote de 100 fotos y una pieza translúcida (F8).

Correcciones incluidas: (1) el worker reutilizaba la máscara del proceso anterior en cada reproceso, así que BiRefNet nunca volvía a correr; ahora solo se reutiliza la corregida a mano (`mask_edited`). (2) La vista del lote mostraba claves crudas para los estados de imagen (`batches.status.pending`). (3) La vista creaba una consulta nueva por cada evento SSE; ahora invalida la misma y filtra por lote. (4) `GET /files/{key}` fuera del almacenamiento responde 404 (se había perdido al unir F3.2). (5) Ajustes > Procesamiento por defecto usa el mismo formulario que crear lote, en vez de editar formatos y sombra como texto o JSON.

---

## Fase 7 — Entradas extra: bot de Telegram y carpeta vigilada (Codex)

- [ ] F7.1 `telegram_bot.py` (long polling, sin servidor público): recibe fotos enviadas **como archivo** (avisa si llegan comprimidas), álbumes y enlaces de Google Photos o Drive. El texto del mensaje define nombre y SKU (`Dragón articulado | SKU: DRG-01`).
- [ ] F7.2 Comandos: `/nuevo <nombre>` (lote nuevo), `/estado`, `/opciones` (líneas de capa y sombra) y `/enviar` (devuelve los resultados como archivos o como `.zip`).
- [ ] F7.3 Restringir el bot a los chat IDs autorizados en `settings`.
- [ ] F7.4 `hot_folder.py`: vigila `data/inbox/`; cada subcarpeta es un lote (con su nombre), procesa con las opciones por defecto y deja el resultado en `data/outbox/<lote>/`.

**Criterio de salida:** enviar 10 fotos al bot desde el celular devuelve las 10 procesadas en el chat.

---

## Fase 8 — Validación con lote real (Claude + usuario)

- [~] F8.1 Procesar un lote real de unas 100 fotos y medir el tiempo total y por imagen. — (claude) 2026-10-27, 35 fotos de `Photos-1-001` (27 de 12 MP) en la GTX 1660, con tienda + Instagram 4:5 y las dos variantes: **3 min 52 s, 6,6 s por foto** (100 fotos ≈ 11 min). Cero fallos. Falta repetirlo con 100.
- [x] F8.2 Revisar el porcentaje "para revisar" y ajustar los umbrales de `quality.py`. — (claude) 2 de 35 (6 %), las dos con razón: una foto de 800×800 (`low_resolution`) y una con los pies cortados por el encuadre (`touches_border`). Revisadas a ojo las 35: recortes correctos también con fondos de cocina, madera y mantel con flores, piezas metálicas y extremidades finas. Los umbrales se quedan como están.
- [ ] F8.3 Subir el `.zip` de storefront con el importador masivo del `ecommerce-dashboard` y verificar que cada foto cae en su producto por SKU.
- [ ] F8.4 Verificar en el storefront y en una vista previa de Instagram que se ven naturales.
- [ ] F8.5 Documentar en el README el flujo final y los problemas conocidos.

**Criterio de salida:** el usuario aprueba el resultado del lote real.

---

## Fase 9 — Nube (opción C) e integración con el ecommerce

Parte del alcance desde el 2026-10-26. Las interfaces ya existen (`JobQueue`, `Storage`, `DATABASE_URL`, `SECRET_KEY`), así que esta fase agrega implementaciones, no reescribe.

- [ ] F9.1 `RedisJobQueue` (Redis ya está en el `docker-compose.yml` raíz) con los mismos tests de contrato que la cola SQLite. Se elige con `QUEUE_BACKEND=redis`.
- [ ] F9.2 `S3Storage` (S3, R2, Spaces o MinIO) con URLs firmadas. Se elige con `STORAGE_BACKEND=s3`.
- [ ] F9.3 Soporte de PostgreSQL vía `DATABASE_URL` (migraciones probadas en ambos motores).
- [ ] F9.4 Autenticación: usuarios con roles (admin, operador) y API keys para integraciones; obligatoria cuando `public_base_url` no es localhost. El bot de Telegram sigue restringido por chat ID.
- [ ] F9.5 Docker: imagen CUDA para API + worker, imagen de la web estática y servicio `image-studio` en el perfil `apps` del `docker-compose.yml` raíz (con `--gpus all`).
- [ ] F9.6 Webhook de Telegram como alternativa al long polling cuando haya URL pública (configurable en Ajustes).
- [ ] F9.7 Backend de proceso remoto opcional (servidor con GPU o fal.ai/Replicate) para cuando no haya GPU local, elegible en Ajustes > Modelos.
- [ ] F9.8 Integración con `ecommerce-dashboard`: botón "Mejorar fotos" en productos que crea un lote vía API key y asigna las aprobadas al producto por SKU.

## Fase 10 — Mejora de resolución (Claude + Codex)

Objetivo: que las fotos pequeñas o reenviadas por WhatsApp suban de resolución sin "dañarse" (sin texturas inventadas ni aspecto de plástico).

**Resultado de la comparación (2026-10-27, claude).** Seis piezas de fotos reales de 12 MP se redujeron a 600 px de lado largo (limpias y con JPEG calidad 72, como WhatsApp) y se volvieron a agrandar a 1640 px (la pieza en el formato tienda), midiendo contra la pieza real:

| Modelo (+ detalle) | SSIM limpia | SSIM WhatsApp | Nitidez vs. real | s/pieza | Licencia |
|---|---|---|---|---|---|
| **4x NMKD Siax + 60 %** | **0,944** | **0,909** | 0,68 | 4,1 | WTFPL |
| Lanczos (sin IA) | 0,940 | 0,899 | 0,33 (borrosa) | 0 | — |
| 4x Nomos8kDAT + 60 % | 0,936 | 0,905 | 0,58 | 26 | CC-BY-4.0 |
| 4x RealESRGAN x4plus + 60 % | 0,930 | 0,899 | 0,63 | 4,0 | BSD-3 |
| 4x-UltraSharp + 60 % | 0,926 | 0,901 | 0,97 | 4,1 | **CC-BY-NC-SA** (no comercial) |
| RealESRGAN x2plus + 60 % (el de antes) | 0,924 | 0,897 | 0,52 | 1,2 | BSD-3 |

Barrido de fidelidad con Siax: la calidad es casi igual entre 50 % y 80 % (SSIM 0,943–0,944); con 50 % la nitidez (0,79) queda más cerca de la real. Sin reinyección los modelos inventan texturas (UltraSharp dibuja grietas negras; Siax, arrugas en fotos con JPEG). Ninguno recupera las líneas de capa que la foto pequeña ya no tiene: el límite real es la captura. En el proceso completo, Siax tarda 6–12 s más que x2plus solo en las fotos que necesitan agrandarse (2 de 35 en la Fase 8).

- [x] F10.1 Catálogo de modelos (`app/pipeline/catalog.py`): `realesrgan_x2plus` y `nmkd_siax`, con URL, SHA-256 y licencia. Siax queda por defecto y `detail_reinjection` baja de 0,6 a 0,5. Se descartan Nomos8kDAT (no mejora y tarda 6 veces más), x4plus (peor que Siax en todo) y UltraSharp (licencia no comercial).
- [x] F10.2 El ampliador acepta modelos x2 y x4 de spandrel y siempre hace al menos una pasada (antes, entre 1,05x y 1,4x se cargaba el modelo pero no se usaba).
- [x] F10.3 `ProcessOptions.upscale_fidelity` (0–100 o `null` = Ajustes) y `GET /settings/upscale-models` (id, escala, tamaño, licencia, instalado). Si el modelo elegido no está descargado, la imagen falla con el comando para descargarlo.
- [x] F10.4 `python -m scripts.download_models --upscale <ids|all>` (por defecto, el modelo por defecto) y README.
- [x] F10.5 (codex) Ajustes > Proceso: `upscale_model` como selector con las opciones de `GET /settings/upscale-models` más "Sin IA (Lanczos)"; las no instaladas se muestran deshabilitadas con el comando de descarga. `detail_reinjection` como deslizador 0–100 %. Hoy los dos son campos de texto. — (codex, 2026-10-27)
- [x] F10.6 (codex) En `ProcessOptionsFields` (crear lote, Ajustes > Procesamiento por defecto y ajustes por foto del visor): deslizador "Fidelidad al agrandar" para `upscale_fidelity` con la opción "Usar la de Ajustes" (`null`) y una ayuda corta: más alto = más fiel a la foto, más bajo = más nitidez reconstruida por la IA. Agregar `upscale_fidelity: null` a `FALLBACK_OPTIONS`. Textos en español e inglés. — (codex, 2026-10-27)
- [x] F10.7 (codex) Tests de componentes de F10.5 y F10.6, y `tsc -b`, `eslint` y `vitest` en verde. — (codex, 2026-10-27)

**Criterio de salida:** desde la web se elige el modelo y la fidelidad, y una foto reenviada por WhatsApp sale para la tienda sin texturas inventadas.

## Fase 11 — Escenas: que la pieza no flote (Claude + Codex)

Objetivo: además del fondo blanco, poner la pieza apoyada en una escena. El usuario eligió (2026-10-27) los cuatro estilos y que **todos los formatos** (tienda e Instagram) usen la escena; cada lote o foto puede cambiarla.

Todo se dibuja con código, sin IA generativa: la pieza nunca cambia y cada escena tarda menos de 1 s. Lo que la "apoya" es la oclusión de contacto (sombra fina y oscura pegada a la base) más una penumbra amplia; en estudio y color, además, un reflejo tenue. Probado con el proceso completo (máscara guardada + Siax) en tres piezas de la Fase 8: unos 2 s por foto con dos formatos.

| Estilo | Qué es |
|---|---|
| `white` | El fondo liso de antes (`export.background_hex`) |
| `studio` (por defecto) | Pared que se curva hacia el piso sin línea visible, sombra de contacto y reflejo |
| `pedestal` | Base redonda de exhibición dibujada con luz y sombra; la pieza se apoya sobre la tapa |
| `color` | Como estudio, con pared y piso derivados de un solo color de marca |
| `photo` | Una foto de la biblioteca (por ejemplo, la mesa del usuario); la pieza se apoya en el punto marcado |

Límite conocido: si la pieza se fotografió inclinada, la escena no lo corrige (el punto más bajo de la máscara es el que se apoya).

- [x] F11.1 `app/pipeline/scene.py`: `render_scene` con estudio, pedestal, color y foto. La base queda en el 80 % del alto (estudio y color), sobre la tapa del pedestal (70 %) o en el punto marcado de la foto; la foto cubre el lienzo y se recorta para conservar ese punto. `original_hd` con escena usa un lienzo 4:5.
- [x] F11.2 Contratos: `ProcessOptions.scene` y `ProcessOptions.background_id` (`null` = Ajustes), `ExportSettings.scene: SceneSettings` y `SceneBackground` / `SceneBackgroundUpdate`. El modo de sombra también gobierna la escena (`none` = sin sombra; `strong` = 1,3×) junto con `shadow_intensity`.
- [x] F11.3 Biblioteca de fondos: tabla `backgrounds` (migración `0004`) y `GET/POST /backgrounds`, `PATCH/DELETE /backgrounds/{id}`. El primer fondo subido queda como predeterminado; al borrarlo se limpia `default_background_id`. Valida igual que las subidas (bomba de descompresión, formatos, `max_download_mb`).
- [x] F11.4 El worker resuelve la foto de fondo (`options.background_id` o el predeterminado) y, si no existe, la imagen falla con un mensaje claro.
- [x] F11.5 Tests (`tests/test_scenes.py`): apoyo en el piso, sombra, reflejo, pedestal, foto, HD 4:5, API de la biblioteca. `schema.d.ts` ya regenerado en la rama.
- [x] F11.6 (codex) Ajustes > Exportación: sección "Escena" con el estilo (5 opciones con su nombre traducido), selectores de color para `studio_wall_hex`, `studio_floor_hex`, `brand_hex` y `pedestal_hex` (`<input type="color">`), deslizador de reflejo 0–60 % y el fondo predeterminado (miniaturas de la biblioteca). Hoy `scene` aparece como JSON crudo en un campo de texto: que `SettingField` no lo pinte. — (codex, 2026-10-27)
- [ ] F11.7 (codex) Biblioteca de fondos en Ajustes: subir (`POST /backgrounds`, multipart `file` + `name`), renombrar, borrar con confirmación y **marcar el punto de apoyo** con un clic sobre la foto (`floor_y`, `center_x` = coordenadas del clic en fracción) más un deslizador de tamaño de la pieza (`piece_height`, 20–90 %). Mostrar una silueta o marca en el punto para que se vea dónde quedará la base.
- [ ] F11.8 (codex) En `ProcessOptionsFields` (crear lote, procesamiento por defecto y ajustes por foto): selector "Fondo" con "Usar el de Ajustes" (`null`) más los 5 estilos y, si es `photo`, el selector de foto de la biblioteca (`background_id`, `null` = la predeterminada). Agregar `scene: null` y `background_id: null` a `FALLBACK_OPTIONS`. Textos en español e inglés.
- [ ] F11.9 (codex) Tests de componentes de F11.6–F11.8, `tsc -b`, `eslint`, `vitest` y una prueba real: subir una foto de una mesa, marcar el punto, reprocesar una foto con `photo` y verla en la galería.

**Criterio de salida:** desde la web se elige el estilo (y la foto de fondo con su punto de apoyo), y las fotos salen apoyadas, sin efecto de flotar, en todos los formatos.

---

## Qué necesitamos del usuario y cuándo

| Cuándo | Qué |
|---|---|
| **Al empezar la Fase 1** (lo antes posible) | **10 a 20 fotos reales** en `image-studio/samples/`: alguna pieza blanca, alguna translúcida, una con varias piezas, una fotografiada sobre la cama de la impresora y piezas de colores. Sirven para ajustar el proceso con casos reales desde el principio |
| Al cerrar la Fase 1 | Aprobar la hoja de contacto antes/después (estilo de sombra, margen y líneas de capa) |
| Fase 4 | Un enlace real de álbum de Google Photos para probar el importador |
| Fase 5 | Crear un bot con @BotFather y pasar el token y tu chat ID (se guardan en ajustes, no en el código) |
| Fase 8 | El lote grande de unas 100 fotos y los SKU de los productos |

---

## Notas y bloqueos

_(Agregar aquí cualquier hallazgo que cambie el plan, con fecha y agente.)_

- **2026-10-26 · claude · BiRefNet necesita `trust_remote_code`.** El modelo de Hugging Face trae su arquitectura como código Python del repositorio. Los pesos ya están descargados con la revisión fijada, pero **no se ha ejecutado**: el usuario debe decidir antes de la Fase 1 entre (a) revisar y permitir ese código de la revisión fijada `e2bf8e4…`, o (b) usar la versión ONNX de BiRefNet (`onnxruntime-gpu`, sin código remoto, quizá algo más lenta). Real-ESRGAN carga con `spandrel` sin código remoto.
- **2026-10-26 · claude · `openapi-typescript` y TypeScript 6.** `openapi-typescript@7` declara TS 5 como dependencia par; se resolvió con `overrides` en `web/package.json`. Funciona: `npm run gen:api` genera los tipos.
- **2026-10-26 · claude · Consola de Windows.** Los scripts imprimen tildes que la consola cp1252 muestra mal; es solo visual.
- **2026-10-27 · claude · Pista para F4.2 (Google Photos), probada a mano.** `photos.app.goo.gl/...` redirige (302) a `photos.google.com/share/<id>?key=...`. El HTML (con User-Agent de navegador) trae en `AF_initDataCallback({key: 'ds:1'...})` cada foto como `["AF1Qip<id>",["https://lh3.googleusercontent.com/pw/<token>",<ancho>,<alto>,...]`. Sumando `=d` a la URL se descarga el JPEG original con su EXIF (probado: 3000×4000, 3,1 MB). El primer `AF1Qip…` es el álbum, no una foto. Falta comprobar con álbumes grandes si el HTML inicial trae todas las fotos o si hay que paginar.
- **2026-10-27 · claude · Decisión BiRefNet (confirmada por el usuario):** copiar el código de la arquitectura (MIT) a `backend/app/pipeline/vendor/birefnet/`, revisado y fijado, y cargar los pesos `safetensors` ya descargados. Sin `trust_remote_code` ni un segundo motor (ONNX queda como plan B). Hecho en F1.1. Pendiente para F1.8: la métrica `uncertain_edge_ratio` dio 0,60 en una foto con bordes correctos, así que hay que calibrarla (banda de borde proporcional al tamaño) antes de usarla para marcar "para revisar".

## Registro de cambios de contrato

_(Fecha · agente · cambio · motivo. El otro agente marca "revisado".)_

- 2026-10-26 · claude · Contratos iniciales congelados (`app/contracts/`), más `AppSettings` (toda la configuración editable) y `process_image(..., *, base_name, mask_override)`. Motivo: cierre de la Fase 0 con alcance de la opción C. Revisado por codex: [x]
- 2026-10-27 · codex · Se agregan `AppSettingsPublic` y `TelegramTestResult` para documentar la vista enmascarada de ajustes y el resultado de la prueba de Telegram. Motivo: F2.9 requiere que OpenAPI describa respuestas sin secretos. Revisado por claude: [x]
- 2026-10-27 · claude · (rama `feat/F1-pipeline`) `process_image` recibe `settings: AppSettings | None = None` (el worker ya lo pasa; quitar el `del settings` de `PipelineProcessor` al unir). `QualitySettings.low_confidence_edge_ratio` por defecto pasa de 0,15 a 0,6 (calibrado con 12 fotos reales). `ImageItem.review_reasons` usa los códigos de F1.8 (la web debe traducirlos). Con `generate_both_layer_variants` el proceso nombra `SKU.webp` (conservar) y `SKU_smooth.webp` (suavizar). Revisado por codex: [x]
- 2026-10-27 · claude · `ProcessOptions.shadow_intensity: int` (0 a 200, por defecto 100) escala la opacidad del modo de sombra; en `main` desde `feat/F1.13-shadow-intensity`. **Codex:** regenerar `web/src/shared/api/schema.d.ts` (`npm run gen:api`) e incluir en los formularios de opciones (F3.2 crear lote, F3.6 Ajustes > Procesamiento por defecto) y en el panel por imagen (F6.3) todos los campos de `ProcessOptions`: formatos, líneas de capa + intensidad, sombra + intensidad, margen (`fill_ratio`), agrandado máximo, balance de blancos y las dos variantes. Revisado por codex: [x]
- 2026-10-27 · claude · Fase 6 (rama `feat/F6-review-gallery`): `ProcessOptions.rotate` (0/90/180/270, horario) y `ProcessOptions.crop: CropBox | None` (fracciones de la foto ya girada) se aplican antes de segmentar; la máscara se guarda siempre en coordenadas del original. `ImageItem.selected_variant` y `ImageItem.mask_edited` (migración `0003`). Nuevos: `ApproveRequest` (`POST /images/{id}/approve` con `{variant}`: el `.zip` exporta solo esa variante y sin sufijo), `BulkImagesRequest` (`POST /batches/{id}/images/approve` y `/reprocess`), `DELETE /images/{id}/mask` (descarta la corrección a mano) y `GET /files/{key}?w=320|640|1280` (miniaturas WebP cacheadas). El worker pasa `mask_override` solo si `mask_edited`. El modo stub genera las dos variantes. **Codex:** regenerar `schema.d.ts`; los formularios de opciones deben partir de `FALLBACK_OPTIONS` (`web/src/shared/components/processOptions.ts`) y usar `ProcessOptionsFields`; `rotate` y `crop` son por imagen (no van en crear lote). Revisado por codex: [ ]
- 2026-10-27 · claude · Fase 10 (rama `feat/F10-upscale-models`): `PipelineSettings.upscale_model` pasa a `"realesrgan_x2plus" | "nmkd_siax" | "lanczos"` con `nmkd_siax` por defecto, y `detail_reinjection` por defecto pasa de 0,6 a 0,5. Nuevos: `ProcessOptions.upscale_fidelity: int | None` (0–100), `UpscaleModelInfo` y `GET /settings/upscale-models`. `schema.d.ts` ya regenerado en la rama. **Codex:** F10.5–F10.7. Revisado por codex: [x]
- 2026-10-27 · codex · `Job.payload` expone el payload persistido de la cola para que el worker procese importaciones; los fallos de un trabajo `import` marcan el lote como `failed` y publican `batch.finished`. Motivo: corrección F4.7 de importaciones bloqueadas. Revisado por codex: [x]
- 2026-10-27 · claude · Fase 11 (rama `feat/F11-scenes`): nuevos `SceneStyle` (`white|studio|pedestal|color|photo`), `ProcessOptions.scene` y `ProcessOptions.background_id` (ambos `null` = Ajustes), `ExportSettings.scene: SceneSettings` (estilo por defecto `studio`), `SceneBackground`, `SceneBackgroundUpdate` y `GET/POST /backgrounds`, `PATCH/DELETE /backgrounds/{id}` (tabla `backgrounds`, migración 0004). El fondo por defecto deja de ser blanco puro: para volver al de antes, `export.scene.style = "white"`. `schema.d.ts` ya regenerado. **Codex:** F11.6–F11.9. Revisado por codex: [ ]
