"""Avisos de Telegram desacoplados del worker mediante el bus de eventos."""

import logging
from collections.abc import Callable
from typing import Protocol

import httpx

from app.contracts import AppSettings, Event

logger = logging.getLogger(__name__)


class EventSink(Protocol):
    def publish(self, event: Event) -> int: ...


class TelegramNotifier:
    def __init__(self, sink: EventSink, settings_loader: Callable[[], AppSettings]) -> None:
        self.sink = sink
        self.settings_loader = settings_loader
        self._started: set[str] = set()
        self._last_progress: dict[str, int] = {}

    def publish(self, event: Event) -> int:
        event_id = self.sink.publish(event)
        settings = self.settings_loader()
        self._notify(settings, event)
        return event_id

    def _notify(self, settings: AppSettings, event: Event) -> None:
        telegram = settings.telegram
        if not telegram.enabled or telegram.bot_token is None:
            return
        batch_id = str(event.payload.get("batch_id", ""))
        if not batch_id:
            return
        message: str | None = None
        if (
            event.type == "image.updated"
            and event.payload.get("status") == "processing"
            and batch_id not in self._started
        ):
            self._started.add(batch_id)
            if telegram.notify_on_start:
                message = f"Image Studio: lote iniciado ({event.payload.get('batch_name', batch_id)})."
        elif event.type == "batch.progress" and telegram.notify_progress_step:
            counts = event.payload.get("counts", {})
            total = int(counts.get("total", 0)) if isinstance(counts, dict) else 0
            done = int(counts.get("done", 0)) if isinstance(counts, dict) else 0
            review = int(counts.get("review", 0)) if isinstance(counts, dict) else 0
            failed = int(counts.get("failed", 0)) if isinstance(counts, dict) else 0
            percent = round((done + review + failed) * 100 / total) if total else 0
            step = (percent // telegram.notify_progress_step) * telegram.notify_progress_step
            if step and step > self._last_progress.get(batch_id, 0):
                self._last_progress[batch_id] = step
                message = f"Image Studio: lote {batch_id} al {step} %."
        elif event.type == "batch.finished" and telegram.notify_on_finish:
            counts = event.payload.get("counts", {})
            done = int(counts.get("done", 0)) if isinstance(counts, dict) else 0
            review = int(counts.get("review", 0)) if isinstance(counts, dict) else 0
            failed = int(counts.get("failed", 0)) if isinstance(counts, dict) else 0
            name = event.payload.get("batch_name", batch_id)
            url = settings.general.public_base_url.rstrip("/")
            gallery = f"\n{url}/batches/{batch_id}" if url else ""
            message = (
                f"Image Studio: {name}: {done} listas, {review} para revisar, {failed} fallidas.{gallery}"
            )
        if message:
            for chat_id in telegram.notify_chat_ids:
                self._send(telegram.bot_token.get_secret_value(), chat_id, message)

    @staticmethod
    def _send(token: str, chat_id: int, text: str) -> None:
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("No se pudo enviar el aviso de Telegram")
