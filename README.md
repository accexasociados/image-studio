# Image Studio

Convierte fotos de piezas de **impresión 3D** en fotos de producto con **fondo blanco**, buena resolución y acabado natural, listas para el storefront e Instagram. La IA solo recorta y mejora la resolución: nunca regenera la pieza.

Plan y estado: [PLAN_EJECUCION.md](PLAN_EJECUCION.md). Reglas para agentes: [AGENTS.md](AGENTS.md).

## Requisitos

- Windows 11, Python **3.11** (`py -3.11`), Node 20+.
- GPU NVIDIA con driver reciente (probado: GTX 1660, 6 GB). Sin GPU funciona en CPU, mucho más lento.

## Instalación

```powershell
# Backend
cd backend
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
# 1) PyTorch con CUDA (antes que el resto)
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
# 2) Proyecto + modelos de IA + herramientas de desarrollo
.venv\Scripts\python -m pip install -e ".[ml,dev]"
# 3) Verificar GPU y descargar pesos (~1 GB a ../models)
.venv\Scripts\python -m scripts.check_gpu
.venv\Scripts\python -m scripts.download_models
# Opcional: otros modelos de ampliación para elegir en Ajustes > Proceso (--upscale all o por coma)
.venv\Scripts\python -m scripts.download_models --upscale all

# Web
cd ..\web
npm install
```

Sin GPU o para trabajar solo en la API y la web: instala `pip install -e ".[dev]"` (sin `ml`) y usa `PIPELINE_MODE=stub`.

## Uso en desarrollo

```powershell
copy .env.example .env      # opcional: todo tiene valor por defecto
.\scripts\dev.ps1           # API + worker + web; Ctrl+C cierra los tres
```

Para validar las dependencias sin iniciar servicios: `.\scripts\dev.ps1 -Check`. Los logs de cada
proceso se guardan en una carpeta temporal que el script muestra al arrancar.

- API: `http://localhost:8090/api/v1` · Swagger: `http://localhost:8090/docs`
- La base SQLite se crea y migra sola al arrancar la API (`data/studio.db`).

## Configuración

- `.env`: solo arranque (puertos, rutas, dispositivo, conexión a BD/Redis/S3 y `SECRET_KEY`). Ver [.env.example](.env.example).
- Todo lo demás se edita desde la web (**Ajustes**) y se guarda en la tabla `settings`: Telegram, avisos, formatos de salida, importadores, carpeta vigilada, modelos y umbrales de calidad. Los secretos se guardan cifrados.

## Comandos de verificación

```powershell
# backend/
.venv\Scripts\python -m pytest
.venv\Scripts\ruff check . ; .venv\Scripts\ruff format .
.venv\Scripts\mypy app scripts

# web/
npm run lint ; npm run test ; npm run build
npm run gen:api   # regenera src/shared/api/schema.d.ts (API corriendo en 8090)
```
