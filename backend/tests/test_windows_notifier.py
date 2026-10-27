from app.contracts import AppSettings, Event
from app.notifiers.windows import WindowsNotifier


class Sink:
    def publish(self, event: Event) -> int:
        return 1


def test_windows_notifier_delegates_event(monkeypatch) -> None:
    calls: list[Event] = []
    monkeypatch.setattr(WindowsNotifier, "notify_finished", lambda event: calls.append(event))
    settings = AppSettings()
    settings.notifications.windows_toast = True
    notifier = WindowsNotifier(Sink(), lambda: settings)
    notifier.publish(Event(type="batch.finished", payload={"batch_id": "b1", "counts": {}}))
    assert len(calls) == 1
