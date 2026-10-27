from fastapi import APIRouter

from app import __version__
from app.config import get_settings
from app.contracts import Health
from app.gpu import detect_gpu

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health() -> Health:
    settings = get_settings()
    return Health(
        status="ok",
        version=__version__,
        pipeline_mode=settings.pipeline_mode,
        device=settings.device,
        gpu=detect_gpu(),
    )
