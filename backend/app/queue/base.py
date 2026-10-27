"""Interfaz de la cola de trabajos. Implementaciones: SQLite (local, Fase 2) y Redis (nube, Fase 9).
La web, el bot de Telegram y la carpeta vigilada solo encolan; el worker consume."""

from typing import Any, Protocol

from app.contracts import Job, JobKind


class JobQueue(Protocol):
    def enqueue(
        self,
        kind: JobKind,
        *,
        image_id: str | None = None,
        batch_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Job: ...

    def claim_next(self, worker_id: str) -> Job | None:
        """Toma el trabajo más antiguo en estado `queued` y lo marca `running` de forma atómica."""
        ...

    def complete(self, job_id: str) -> None: ...

    def fail(self, job_id: str, error: str, *, retry: bool) -> None: ...

    def cancel_batch(self, batch_id: str) -> int:
        """Cancela los trabajos pendientes de un lote y devuelve cuántos canceló."""
        ...

    def recover_stale(self) -> int:
        """Devuelve a `queued` los trabajos que quedaron `running` tras un reinicio del worker."""
        ...
