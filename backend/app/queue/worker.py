import argparse
import logging
import os
import re
import socket
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Protocol
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts import AppSettings, Event, Job, ProcessOptions, ProcessResult
from app.db.models import BatchRow, ImageRow, OutputRow, utcnow
from app.db.session import get_sessionmaker
from app.db.settings_store import load_settings
from app.events import EventPublisher, get_event_store
from app.gpu import release_gpu_memory
from app.importers.direct_url import download_image
from app.importers.google_drive import download_drive
from app.importers.google_photos import download_album
from app.notifiers.telegram import TelegramNotifier
from app.notifiers.windows import WindowsNotifier
from app.pipeline.run import process_image
from app.queue import JobQueue, get_job_queue
from app.storage import Storage, get_storage

logger = logging.getLogger(__name__)
_TERMINAL_IMAGE_STATUSES = {"done", "review", "failed", "approved"}


class ImageProcessor(Protocol):
    def __call__(
        self,
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult: ...


class PipelineProcessor:
    """Adaptador único del proceso; su instancia vive durante toda la vida del worker."""

    def __call__(
        self,
        input_path: Path,
        options: ProcessOptions,
        out_dir: Path,
        *,
        base_name: str,
        mask_override: Path | None,
        settings: AppSettings,
    ) -> ProcessResult:
        return process_image(
            input_path,
            options,
            out_dir,
            base_name=base_name,
            mask_override=mask_override,
            settings=settings,
        )


@dataclass(frozen=True)
class _ImageContext:
    image_id: str
    batch_id: str
    input_path: Path
    mask_override: Path | None
    options: ProcessOptions
    base_name: str
    settings: AppSettings


class Worker:
    """Consumidor secuencial: una instancia procesa un trabajo a la vez."""

    def __init__(
        self,
        *,
        worker_id: str,
        queue: JobQueue,
        storage: Storage,
        processor: ImageProcessor,
        release_memory: Callable[[], None] = release_gpu_memory,
        publisher: EventPublisher | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.queue = queue
        self.storage = storage
        self.processor = processor
        self.release_memory = release_memory
        self.publisher = publisher

    def run_once(self) -> bool:
        job = self.queue.claim_next(self.worker_id)
        if job is None:
            return False

        try:
            self._process(job)
        except JobCancelled:
            self.queue.cancel_job(job.id)
        except Exception as error:
            logger.exception("Falló el trabajo %s", job.id)
            self._record_failure(job, error, retry=job.kind in {"process", "reprocess"})
        return True

    def run(self, *, poll_seconds: float = 1.0, once: bool = False) -> None:
        recovered = self.queue.recover_stale()
        if recovered:
            logger.warning("Se recuperaron %d trabajos interrumpidos.", recovered)
        while True:
            claimed = self.run_once()
            if once:
                return
            if not claimed:
                time.sleep(poll_seconds)

    def _process(self, job: Job) -> None:
        if job.kind == "import":
            self._process_import(job)
            return
        if job.kind not in {"process", "reprocess"} or job.image_id is None:
            raise ValueError(f"Tipo de trabajo no soportado por este worker: {job.kind}")
        context = self._load_context(job.image_id)
        self._publish_state(context.image_id)

        with TemporaryDirectory(prefix=f"image-studio-{job.id}-") as temp_dir:
            temp_root = Path(temp_dir)
            try:
                result, result_dir = self._invoke(context, temp_root / "first")
            except Exception as error:
                reduced = _reduced_tile_settings(context.settings)
                if not _is_cuda_out_of_memory(error) or reduced is None:
                    raise
                logger.warning(
                    "Memoria CUDA agotada en %s; reintento con tiles de %d px.",
                    job.id,
                    reduced.pipeline.tile_size,
                )
                self.release_memory()
                retry_context = _ImageContext(
                    image_id=context.image_id,
                    batch_id=context.batch_id,
                    input_path=context.input_path,
                    mask_override=context.mask_override,
                    options=context.options,
                    base_name=context.base_name,
                    settings=reduced,
                )
                result, result_dir = self._invoke(retry_context, temp_root / "reduced-tiles")

            persisted = self._persist_result(context, result, result_dir)
        if persisted:
            self.queue.complete(job.id)
        else:
            self.queue.cancel_job(job.id)
        self._publish_state(context.image_id)

    def _process_import(self, job: Job) -> None:
        if job.batch_id is None or not isinstance(job.payload.get("url"), str):
            raise ValueError("El trabajo de importación no tiene lote o URL.")
        url = job.payload["url"]
        with get_sessionmaker()() as session:
            settings = load_settings(session)
            if "photos.google.com" in url or "photos.app.goo.gl" in url:
                images = download_album(url)
            elif "drive.google.com" in url:
                key = settings.importers.google_drive_api_key
                images = download_drive(url, api_key=key.get_secret_value() if key else None)
            else:
                images = (download_image(url),)
            batch = session.get(BatchRow, job.batch_id)
            if batch is None:
                raise ValueError("El lote de importación no existe.")
            imported = 0
            for image in images:
                row = ImageRow(
                    batch_id=batch.id,
                    source="url",
                    source_ref=image.filename,
                    original_path="pending",
                    status="pending",
                    position=len(batch.images) + imported,
                )
                session.add(row)
                session.flush()
                extension = image.filename.rsplit(".", 1)[-1].lower()
                key = f"batches/{batch.id}/originals/{row.id}.{extension}"
                self.storage.save_bytes(key, image.data)
                row.original_path = key
                self.queue.enqueue("process", image_id=row.id, batch_id=batch.id, session=session)
                imported += 1
                if self.publisher:
                    self.publisher.publish(
                        Event(type="import.progress", payload={"batch_id": batch.id, "imported": imported})
                    )
            if imported == 0:
                raise ValueError("El enlace no contiene imágenes.")
            batch.status = "queued"
            batch.finished_at = None
            session.commit()

    def _invoke(self, context: _ImageContext, out_dir: Path) -> tuple[ProcessResult, Path]:
        result = self.processor(
            context.input_path,
            context.options,
            out_dir,
            base_name=context.base_name,
            mask_override=context.mask_override,
            settings=context.settings,
        )
        return result, out_dir

    def _load_context(self, image_id: str) -> _ImageContext:
        with get_sessionmaker()() as session:
            image = session.get(ImageRow, image_id)
            if image is None:
                raise ValueError(f"Imagen no encontrada: {image_id}")
            batch = session.get(BatchRow, image.batch_id)
            if batch is None:
                raise ValueError(f"Lote no encontrado para la imagen: {image_id}")
            if batch.status == "cancelled":
                raise JobCancelled("El lote fue cancelado.")

            image.status = "processing"
            image.error = None
            batch.status = "processing"
            batch.finished_at = None
            settings = load_settings(session)
            options_data = image.options_override or batch.default_options
            context = _ImageContext(
                image_id=image.id,
                batch_id=batch.id,
                input_path=self.storage.local_path(image.original_path),
                # La máscara del proceso anterior no se reutiliza: solo la corregida a mano.
                mask_override=(
                    self.storage.local_path(image.mask_path)
                    if image.mask_edited and image.mask_path
                    else None
                ),
                options=ProcessOptions.model_validate(options_data),
                base_name=_base_name(image),
                settings=settings,
            )
            session.commit()
            return context

    def _publish_state(self, image_id: str) -> None:
        if self.publisher is None:
            return
        try:
            with get_sessionmaker()() as session:
                image = session.get(ImageRow, image_id)
                if image is None:
                    return
                batch = session.get(BatchRow, image.batch_id)
                if batch is None:
                    return
                statuses = session.scalars(select(ImageRow.status).where(ImageRow.batch_id == batch.id)).all()
                counts = {
                    "total": len(statuses),
                    "done": sum(item in {"done", "approved"} for item in statuses),
                    "review": statuses.count("review"),
                    "failed": statuses.count("failed"),
                }
                self.publisher.publish(
                    Event(
                        type="image.updated",
                        payload={"batch_id": batch.id, "image_id": image.id, "status": image.status},
                    )
                )
                self.publisher.publish(
                    Event(
                        type="batch.progress",
                        payload={"batch_id": batch.id, "status": batch.status, "counts": counts},
                    )
                )
                if batch.status in {"done", "failed", "cancelled"}:
                    self.publisher.publish(
                        Event(
                            type="batch.finished",
                            payload={"batch_id": batch.id, "status": batch.status, "counts": counts},
                        )
                    )
        except Exception:
            logger.exception("No se pudo publicar el estado de la imagen %s", image_id)

    def _persist_result(
        self,
        context: _ImageContext,
        result: ProcessResult,
        result_dir: Path,
    ) -> bool:
        with get_sessionmaker()() as session:
            image = session.get(ImageRow, context.image_id)
            batch = session.get(BatchRow, context.batch_id)
            if image is None or batch is None:
                raise ValueError("La imagen o su lote desaparecieron durante el proceso.")
            if batch.status == "cancelled":
                image.status = "pending"
                image.error = "El lote fue cancelado."
                session.commit()
                return False

            current_version = session.scalar(
                select(func.max(OutputRow.version)).where(OutputRow.image_id == image.id)
            )
            version = (current_version or 0) + 1
            result_root = result_dir.resolve()
            for output in result.outputs:
                output_path = _safe_result_path(output.path, result_root)
                relative = output_path.relative_to(result_root).as_posix()
                key = f"batches/{batch.id}/outputs/{image.id}/v{version}/{relative}"
                self.storage.save_bytes(key, output_path.read_bytes())
                session.add(
                    OutputRow(
                        image_id=image.id,
                        preset=output.preset,
                        variant=output.variant,
                        path=key,
                        width=output.width,
                        height=output.height,
                        bytes=output.bytes,
                        version=version,
                    )
                )

            if result.mask_path is not None:
                mask_path = _safe_result_path(result.mask_path, result_root)
                mask_key = f"batches/{batch.id}/masks/{image.id}/v{version}/{mask_path.name}"
                self.storage.save_bytes(mask_key, mask_path.read_bytes())
                image.mask_path = mask_key

            image.review_reasons = result.review_reasons
            image.status = "review" if result.review_reasons else "done"
            image.error = None
            session.flush()
            _refresh_batch_status(session, batch)
            session.commit()
            return True

    def _record_failure(self, job: Job, error: Exception, *, retry: bool) -> None:
        will_retry = retry and job.attempts < 3
        self.queue.fail(job.id, str(error), retry=retry)
        if job.image_id is None:
            return
        with get_sessionmaker()() as session:
            image = session.get(ImageRow, job.image_id)
            if image is None:
                return
            batch = session.get(BatchRow, image.batch_id)
            image.status = "pending" if will_retry else "failed"
            image.error = str(error)
            if batch is not None:
                _refresh_batch_status(session, batch)
            session.commit()
        self._publish_state(job.image_id)


def _safe_result_path(path: str, root: Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"El pipeline devolvió una ruta fuera del directorio temporal: {path}")
    if not resolved.is_file():
        raise ValueError(f"El pipeline no generó el archivo esperado: {path}")
    return resolved


def _refresh_batch_status(session: Session, batch: BatchRow) -> None:
    statuses = session.scalars(select(ImageRow.status).where(ImageRow.batch_id == batch.id)).all()
    if statuses and all(image_status in _TERMINAL_IMAGE_STATUSES for image_status in statuses):
        batch.status = "failed" if all(image_status == "failed" for image_status in statuses) else "done"
        batch.finished_at = utcnow()
    else:
        if batch.status != "cancelled":
            batch.status = "processing"
        batch.finished_at = None


class JobCancelled(Exception):
    """Trabajo descartado porque su lote se canceló."""


def _base_name(image: ImageRow) -> str:
    source_stem = PurePosixPath((image.source_ref or image.id).replace("\\", "/")).stem
    candidate = image.sku or image.product_name or source_stem or image.id
    normalized = unicodedata.normalize("NFKD", candidate).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9._-]+", "-", normalized).strip("-._")
    return slug or image.id


def _is_cuda_out_of_memory(error: Exception) -> bool:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    return "outofmemory" in name or ("cuda" in message and "out of memory" in message)


def _reduced_tile_settings(settings: AppSettings) -> AppSettings | None:
    current = settings.pipeline.tile_size
    if current <= 128:
        return None
    pipeline = settings.pipeline.model_copy(update={"tile_size": max(128, current // 2)})
    return settings.model_copy(update={"pipeline": pipeline})


def _worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:8]}"


def _runtime_settings() -> AppSettings:
    with get_sessionmaker()() as session:
        return load_settings(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker secuencial de Image Studio")
    parser.add_argument("--once", action="store_true", help="Procesa como máximo un trabajo y termina.")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds debe ser mayor que cero")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    event_store = get_event_store()
    telegram = TelegramNotifier(
        event_store,
        _runtime_settings,
    )
    worker = Worker(
        worker_id=_worker_id(),
        queue=get_job_queue(),
        storage=get_storage(),
        processor=PipelineProcessor(),
        publisher=WindowsNotifier(telegram, _runtime_settings),
    )
    try:
        worker.run(poll_seconds=args.poll_seconds, once=args.once)
    except KeyboardInterrupt:
        logger.info("Worker detenido.")


if __name__ == "__main__":
    main()
