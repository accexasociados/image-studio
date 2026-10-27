from app.config import get_settings
from app.db.session import get_sessionmaker
from app.queue.base import JobQueue
from app.queue.sqlite import SQLiteJobQueue


def get_job_queue() -> JobQueue:
    if get_settings().queue_backend == "redis":
        raise NotImplementedError("Cola Redis pendiente (Fase 9).")
    return SQLiteJobQueue(get_sessionmaker())


__all__ = ["JobQueue", "SQLiteJobQueue", "get_job_queue"]
