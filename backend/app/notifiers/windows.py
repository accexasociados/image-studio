"""Notificaciones nativas de Windows sin hacer obligatorio el extra visual."""

import logging
from typing import Protocol

from app.contracts import Event

logger = logging.getLogger(__name__)


class EventSink(Protocol):
    def publish(self, event: Event) -> int: ...


class WindowsNotifier:
    def __init__(self, sink: EventSink, settings_loader) -> None:
        self.sink = sink
        self.settings_loader = settings_loader

    def publish(self, event: Event) -> int:
        event_id = self.sink.publish(event)
        if event.type == "batch.finished" and self.settings_loader().notifications.windows_toast:
            WindowsNotifier.notify_finished(event)
        return event_id

    @staticmethod
    def notify_finished(event: Event) -> None:
        counts = event.payload.get("counts", {})
        title = "Image Studio"
        message = f"Lote terminado: {counts}"
        try:
            from win11toast import toast

            toast(title, message)
        except ImportError:
            logger.info("win11toast no está instalado; se omite el aviso nativo.")
