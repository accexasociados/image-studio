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
| 1 | Proceso de imagen para impresión 3D | Claude | F0 + fotos de prueba | Pendiente |
| 2 | API, cola de trabajos y worker | Codex | F0 | Pendiente |
| 3 | Interfaz web: lotes y subida en bloque | Codex | F0 (API simulada) | Pendiente |
| 4 | Importar desde enlaces (Google Photos, Drive, URL directa) | Codex | F2 | Pendiente |
| 5 | Avisos (Telegram, Windows, navegador) | Codex | F2 | Pendiente |
| 6 | Galería de revisión y editor (antes/después, ajustes, pincel) | Claude | F1, F3 | Pendiente |
| 7 | Entradas extra: bot de Telegram y carpeta vigilada | Codex | F2, F5 | Pendiente |
| 8 | Validación con lote real de 100 fotos y ajuste fino | Claude + usuario | F1–F6 | Pendiente |
| 9 | Nube (opción C): Docker, Redis, S3, autenticación e integración con el ecommerce | Codex (9.1–9.4) + Claude (9.5) | F8 | Pendiente |

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

- [ ] F1.1 `segment.py`: BiRefNet a 1024 px en FP32, máscara escalada al tamaño original con refinado de bordes (guided filter) y bordes suaves de 1 a 2 px. Cerrar huecos pequeños y conservar agujeros reales de la pieza.
- [ ] F1.2 `color.py`: balance de blancos con referencia en el fondo original (que suele ser neutro) y corrección suave de exposición y contraste, solo dentro de la máscara. Nada de saturación agresiva.
- [ ] F1.3 `upscale.py`: Real-ESRGAN x2 por tiles (512 px, solape de 32) en FP32; x4 opcional. **Reinyección de detalle:** mezclar la alta frecuencia de la original (escalada con Lanczos) para conservar las líneas de capa y evitar el aspecto "encerado".
- [ ] F1.4 `layers.py`: modo `keep` (no tocar) y modo `smooth` (filtro guiado o bilateral solo en la pieza, con intensidad 0–100 y bordes protegidos).
- [ ] F1.5 `shadow.py`: sombra de contacto realista (elipse difusa bajo la base, deducida de la parte inferior de la máscara) más una sombra ambiental muy tenue. El modo `auto` usa `strong` si la luminancia media de la pieza es alta (piezas blancas o claras).
- [ ] F1.6 `compose.py`: lienzo `#FFFFFF` puro, centrado por centro de masa, `fill_ratio` según preset y fondo exactamente blanco fuera de la sombra (sin grises residuales).
- [ ] F1.7 `export.py`: los cuatro presets, perfil sRGB, límite de 5 MB para storefront (bajar la calidad hasta cumplirlo) y nombres por SKU o slug.
- [ ] F1.8 `quality.py`: marcar para revisión si la máscara toca el borde de la foto, si la pieza ocupa menos del 5 % o más del 95 %, si hay varias piezas separadas, si los bordes son de baja confianza (translúcidos) o si hay poca diferencia entre la pieza y el fondo.
- [ ] F1.9 `run.py`: modo `real` encadenando las etapas, con tiempos por etapa en `timings_ms`. Las opciones de `AppSettings.pipeline`, `export` y `quality` se reciben como parámetro (sin leer la BD dentro del proceso). El modo `stub` ya existe desde la Fase 0.
- [ ] F1.10 `scripts/process_folder.py`: CLI `python -m scripts.process_folder samples/ out/ --preset storefront --layers keep` para probar sin web.
- [ ] F1.11 Tests con imágenes sintéticas (fondo plano más figura) y prueba de regresión visual básica (fondo blanco puro, pieza centrada, tamaño correcto, < 5 MB).
- [ ] F1.12 Ajuste con las fotos reales: hoja de contacto HTML antes/después en `data/reports/` para que el usuario apruebe el estilo.

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

**Criterio de salida:** subir 100 imágenes en `.zip` crea un lote, el worker las procesa (stub o real), el progreso llega por SSE y el `.zip` de salida se descarga con nombres correctos.

---

## Fase 3 — Interfaz web: lotes y subida en bloque (Codex)

Todo texto visible en **español e inglés** (i18next), sin textos fijos en el código.

- [x] F3.1 Layout base, selector de idioma, tema claro/oscuro y lista de lotes con estado y contadores. — (codex)
- [ ] F3.2 Crear lote: nombre, opciones por defecto (presets, líneas de capa, sombra) y zona de arrastrar y soltar para fotos o `.zip`, con progreso de subida.
- [ ] F3.3 Pestaña "Desde enlace" en el mismo formulario (se conecta en la Fase 4).
- [ ] F3.4 Tabla editable de nombre y SKU por imagen, más carga de CSV.
- [ ] F3.5 Vista del lote en proceso: barra de progreso en vivo (SSE), miniaturas que cambian de estado y filtros (todas, listas, para revisar, fallidas).
- [ ] F3.6 Pantalla de **Ajustes** con una pestaña por sección de `AppSettings`: General, Procesamiento por defecto, Formatos de salida, Telegram (con botón "Probar"), Avisos, Carpeta vigilada, Importadores, Calidad y Modelos. Los secretos se muestran como "Configurado" y se reemplazan sin revelarse.
- [ ] F3.7 Tests de componentes con Vitest + Testing Library.

**Criterio de salida:** flujo completo desde la web: crear lote → subir → ver el progreso → descargar el `.zip`.

---

## Fase 4 — Importar desde enlaces (Codex)

- [ ] F4.1 `direct_url.py`: descarga de una URL de imagen con validación de tipo, límite de tamaño y bloqueo de IPs privadas.
- [ ] F4.2 `google_photos.py`: seguir la redirección de `photos.app.goo.gl/...`, extraer del HTML del álbum compartido las URLs `lh3.googleusercontent.com` y descargarlas en resolución original (sufijo `=d`). Quitar duplicados. **No hay API oficial para álbumes compartidos**: dejar el lector aislado y con test de contrato sobre un HTML guardado, para ajustarlo fácil si Google cambia la página.
- [ ] F4.3 `google_drive.py`: carpeta o archivo público de Drive. Para carpetas, usar la API de Drive con una API key guardada en `settings` (`gdown` limita las carpetas a 50 archivos).
- [ ] F4.4 Endpoint `POST /api/v1/batches/{id}/imports` con `{ url }`: detecta el tipo de enlace, crea un trabajo `import` y reporta progreso por SSE.
- [ ] F4.5 Conexión con la pestaña "Desde enlace" de la web.
- [ ] F4.6 Tests con respuestas simuladas.

**Criterio de salida:** pegar un enlace de álbum de Google Photos de unas 100 fotos crea el lote con todas las imágenes en resolución original.

---

## Fase 5 — Avisos (Codex)

- [ ] F5.1 `telegram.py`: mensajes de "lote iniciado", progreso cada 25 % y "lote terminado: X listas, Y para revisar, Z fallidas", con el enlace local a la galería. Botón "Probar" en ajustes.
- [ ] F5.2 `windows.py`: notificación nativa de Windows al terminar un lote.
- [ ] F5.3 Notificación del navegador al terminar (pidiendo permiso), con la pestaña en segundo plano.
- [ ] F5.4 Suscripción a eventos del worker (sin acoplar los notificadores al proceso de imagen).

**Criterio de salida:** al terminar un lote llegan el mensaje de Telegram y la notificación de Windows.

---

## Fase 6 — Galería de revisión y editor (Claude)

- [ ] F6.1 Galería del lote con cuadrícula, filtros y selección múltiple (aprobar o reprocesar en bloque).
- [ ] F6.2 Comparador antes/después con deslizador y zoom al 100 % para revisar bordes y líneas de capa.
- [ ] F6.3 Panel de ajustes por imagen (líneas de capa e intensidad, sombra, margen, presets) que reprocesa y muestra el resultado.
- [ ] F6.4 Generar ambas variantes de líneas de capa y elegir una.
- [ ] F6.5 Recortar o rotar el original antes de procesar.
- [ ] F6.6 **Pincel de máscara** (sumar o borrar, con tamaño y dureza regulables, deshacer y rehacer) sobre canvas. Guarda la máscara y reprocesa con `mask_override`.
- [ ] F6.7 Atajos de teclado para revisar rápido (A aprobar, R reprocesar, ←/→ navegar).
- [ ] F6.8 Exportar las aprobadas por preset.

**Criterio de salida:** se puede revisar un lote de 100 fotos, corregir una pieza translúcida con el pincel y exportar solo las aprobadas.

---

## Fase 7 — Entradas extra: bot de Telegram y carpeta vigilada (Codex)

- [ ] F7.1 `telegram_bot.py` (long polling, sin servidor público): recibe fotos enviadas **como archivo** (avisa si llegan comprimidas), álbumes y enlaces de Google Photos o Drive. El texto del mensaje define nombre y SKU (`Dragón articulado | SKU: DRG-01`).
- [ ] F7.2 Comandos: `/nuevo <nombre>` (lote nuevo), `/estado`, `/opciones` (líneas de capa y sombra) y `/enviar` (devuelve los resultados como archivos o como `.zip`).
- [ ] F7.3 Restringir el bot a los chat IDs autorizados en `settings`.
- [ ] F7.4 `hot_folder.py`: vigila `data/inbox/`; cada subcarpeta es un lote (con su nombre), procesa con las opciones por defecto y deja el resultado en `data/outbox/<lote>/`.

**Criterio de salida:** enviar 10 fotos al bot desde el celular devuelve las 10 procesadas en el chat.

---

## Fase 8 — Validación con lote real (Claude + usuario)

- [ ] F8.1 Procesar un lote real de unas 100 fotos y medir el tiempo total y por imagen.
- [ ] F8.2 Revisar el porcentaje "para revisar" y ajustar los umbrales de `quality.py`.
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

## Registro de cambios de contrato

_(Fecha · agente · cambio · motivo. El otro agente marca "revisado".)_

- 2026-10-26 · claude · Contratos iniciales congelados (`app/contracts/`), más `AppSettings` (toda la configuración editable) y `process_image(..., *, base_name, mask_override)`. Motivo: cierre de la Fase 0 con alcance de la opción C. Revisado por codex: [x]
- 2026-10-27 · codex · Se agregan `AppSettingsPublic` y `TelegramTestResult` para documentar la vista enmascarada de ajustes y el resultado de la prueba de Telegram. Motivo: F2.9 requiere que OpenAPI describa respuestas sin secretos. Revisado por claude: [ ]
