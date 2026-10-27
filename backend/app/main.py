from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.batches import router as batches_router
from app.api.health import router as health_router
from app.config import get_settings
from app.db.migrate import upgrade_to_head

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    upgrade_to_head()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Image Studio API",
        version=__version__,
        lifespan=lifespan,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"]
    )
    app.include_router(health_router, prefix=API_PREFIX)
    app.include_router(batches_router, prefix=API_PREFIX)
    return app


app = create_app()
