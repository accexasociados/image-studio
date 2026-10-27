# AGENTS.md — Image Studio

Herramienta local (preparada para la nube) que convierte fotos de piezas de impresión 3D en fotos de producto con fondo blanco. Plan, fases, dueños y estado: **`PLAN_EJECUCION.md`**. Léelo completo antes de tocar código, en especial *Protocolo de trabajo entre agentes*.

Proyecto con **su propio repositorio git** dentro del monorepo `accex/abc`: los commits se hacen dentro de `image-studio/`.

## Stack

| Parte | Tecnología |
|---|---|
| `backend/` | Python 3.11 · FastAPI · SQLAlchemy 2 + Alembic (SQLite) · Pydantic 2 · PyTorch CUDA 12.6 · BiRefNet · Real-ESRGAN (`spandrel`) |
| `web/` | Vite 8 · React 19 · TypeScript 6 · Tailwind 4 · TanStack Query · i18next (es/en) · Vitest |

Puertos: API **8090**, web **5180**.

## Comandos

### `backend/` (siempre con el venv; nunca el `python` suelto, que abre la Microsoft Store)
- Crear venv: `py -3.11 -m venv .venv`
- API: `.venv\Scripts\uvicorn app.main:app --port 8090 --reload`
- Tests: `.venv\Scripts\python -m pytest`
- Lint y formato: `.venv\Scripts\ruff check .` · `.venv\Scripts\ruff format .`
- Tipos: `.venv\Scripts\mypy app scripts` (modo estricto)
- Nueva migración: `.venv\Scripts\alembic revision --autogenerate -m "..."` (la API aplica `upgrade head` al arrancar)
- GPU y modelos: `python -m scripts.check_gpu` · `python -m scripts.download_models`

### `web/`
- `npm run dev` · `npm run build` (`tsc -b && vite build`) · `npm run lint` · `npm run test` · `npm run format`
- `npm run gen:api`: regenera `src/shared/api/schema.d.ts` desde el OpenAPI (API corriendo). **Los tipos de la API no se escriben a mano.**

## Arquitectura

- `app/contracts/` es la **fuente de verdad** (Pydantic). Cambiarla exige nota en *Registro de cambios de contrato* del plan.
- `app/pipeline/` no depende de FastAPI ni de la BD: `process_image(input_path, options, out_dir, base_name=..., mask_override=...)`. `PIPELINE_MODE=stub` permite trabajar sin GPU.
- Las entradas (web, bot de Telegram, carpeta vigilada) **solo encolan trabajos**; el worker (concurrencia 1, una GPU) los consume. Interfaz `app/queue/base.py::JobQueue` (SQLite ahora, Redis después).
- Archivos a través de `app/storage` (`Storage`): la BD guarda claves relativas, nunca rutas absolutas, para que funcione igual con disco local o S3.
- Nada de imports de `torch`/`transformers` fuera de `app/pipeline/` y `app/gpu.py` (la API debe arrancar sin el extra `ml`).

## Configuración: env solo para arranque

- `.env` = solo lo necesario antes de abrir la BD: puertos, rutas, `DEVICE`, `PIPELINE_MODE`, `SECRET_KEY`, `DATABASE_URL`, cola, almacenamiento y CORS. Documentar cada variable nueva en `.env.example`.
- **Todo lo demás es configurable desde la web** y vive en `AppSettings` (`app/contracts/settings.py`), guardado por sección en la tabla `settings` con `app/db/settings_store.py`. Telegram, avisos, formatos, importadores, carpeta vigilada, modelos y umbrales: nada de esto se pone fijo en el código ni en `.env`.
- Los secretos (`SecretStr`) se cifran con Fernet y la API nunca los devuelve en claro: solo indica si están configurados. Un secreto nuevo se agrega a `SECRET_FIELDS`.

## Convenciones

- Python: tipado estricto (sin `Any` salvo JSON), ruff (línea de 110), docstrings y comentarios en español, solo donde aportan.
- TypeScript: sin `any`, alias `@/` → `src/`, layout `src/app/` + `src/modules/<feature>/{components,hooks,pages,services,types}` + `src/shared/`, igual que `ecommerce-dashboard`.
- **i18n obligatorio en la web:** todo texto visible en español e inglés en `src/app/i18n/translations.ts` (`es` y `en`; `tsc` falla si no coinciden). Incluye `placeholder`, `aria-label`, `title`, `alt`, toasts y errores. Español con tildes y `¿ ¡`.
- Commits convencionales (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), una rama por tarea (`feat/F2.3-...`). Sin push ni merge a `main` salvo que el usuario lo pida.
- No regenerar el producto con modelos generativos: el proceso solo recorta, mejora la resolución, corrige el color y compone.

## No hacer

- No usar FP16 por defecto (la GTX 1660 da NaN o resultados negros).
- No versionar `data/`, `models/`, `samples/` ni `.env`.
- No tocar carpetas de otra fase que tenga dueño distinto en el plan.
- No ejecutar modelos con `trust_remote_code` de una revisión que no esté fijada en `models/manifest.json`.
