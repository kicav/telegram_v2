from collections import defaultdict
from collections.abc import Callable
from threading import RLock
from ..core.events import DomainEvent


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[DomainEvent], None]]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event_name: str, callback: Callable[[DomainEvent], None]) -> None:
        with self._lock:
            self._subs[event_name].append(callback)

    def publish(self, event: DomainEvent) -> None:
        with self._lock:
            callbacks = list(self._subs.get(event.name, ())) + list(self._subs.get("*", ()))
        for callback in callbacks:
            callback(event)
