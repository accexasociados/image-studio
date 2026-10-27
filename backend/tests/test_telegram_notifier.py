import httpx

from app.contracts import AppSettings, Event
from app.contracts.settings import GeneralSettings, TelegramSettings
from app.notifiers.telegram import TelegramNotifier


class Sink:
    def publish(self, event: Event) -> int:
        return 1


def test_telegram_notifier_sends_start(monkeypatch) -> None:
    settings = AppSettings(telegram=TelegramSettings(enabled=True, bot_token="token", notify_chat_ids=[7]))
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.notifiers.telegram.httpx.post",
        lambda *args, **kwargs: (
            calls.append(kwargs) or httpx.Response(200, request=httpx.Request("POST", "https://telegram"))
        ),
    )
    notifier = TelegramNotifier(Sink(), lambda: settings)
    notifier.publish(Event(type="image.updated", payload={"batch_id": "b1", "status": "processing"}))
    assert calls[0]["json"] == {"chat_id": 7, "text": "Image Studio: lote iniciado (b1)."}


def test_telegram_notifier_reports_review_and_failed_counts(monkeypatch) -> None:
    settings = AppSettings(
        general=GeneralSettings(public_base_url="http://localhost:5180"),
        telegram=TelegramSettings(enabled=True, bot_token="token", notify_chat_ids=[7]),
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.notifiers.telegram.httpx.post",
        lambda *args, **kwargs: (
            calls.append(kwargs) or httpx.Response(200, request=httpx.Request("POST", "https://telegram"))
        ),
    )
    notifier = TelegramNotifier(Sink(), lambda: settings)
    notifier.publish(
        Event(
            type="batch.finished",
            payload={
                "batch_id": "b1",
                "batch_name": "Catálogo",
                "counts": {"total": 3, "done": 1, "review": 1, "failed": 1},
            },
        )
    )
    assert "Catálogo: 1 listas, 1 para revisar, 1 fallidas." in calls[0]["json"]["text"]
    assert "http://localhost:5180/batches/b1" in calls[0]["json"]["text"]
