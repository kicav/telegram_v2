from collections import deque
from threading import Lock
from ..core.events import DomainEvent


class EventAggregator:
    """Coalesces noisy progress events before the UI consumes them."""
    def __init__(self, max_recent: int = 500) -> None:
        self._events: deque[DomainEvent] = deque(maxlen=max_recent)
        self._latest_progress: dict[str, DomainEvent] = {}
        self._lock = Lock()

    def push(self, event: DomainEvent) -> None:
        with self._lock:
            if event.name.endswith("Progress"):
                key = str(event.payload.get("job_id", event.name))
                self._latest_progress[key] = event
            else:
                self._events.append(event)

    def drain(self) -> list[DomainEvent]:
        with self._lock:
            out = list(self._events) + list(self._latest_progress.values())
            self._events.clear()
            self._latest_progress.clear()
            return out
