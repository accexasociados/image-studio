from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings
from app.db.session import get_engine, get_sessionmaker
from app.gpu import detect_gpu
from app.storage import get_storage


def _clear_caches() -> None:
    for cached in (get_settings, get_engine, get_sessionmaker, get_storage, detect_gpu):
        cached.cache_clear()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Cada test usa su propio DATA_DIR, BD SQLite y llave de cifrado, con el proceso en modo stub."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PIPELINE_MODE", "stub")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _clear_caches()
    yield tmp_path
    get_engine().dispose()
    _clear_caches()
