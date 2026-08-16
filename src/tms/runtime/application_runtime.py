from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .db_writer import DBWriter
from .event_aggregator import EventAggregator
from .event_bus import EventBus
from .network_runtime import NetworkRuntime
from .resource_governor import ResourceGovernor
from .worker_pool import WorkerPool


@dataclass(slots=True)
class ApplicationRuntime:
    network: NetworkRuntime
    governor: ResourceGovernor
    events: EventBus
    ui_events: EventAggregator
    workers: WorkerPool
    db_writer: DBWriter
    _network_shutdown_hooks: list[Callable[[], Awaitable[None]]] = field(default_factory=list)

    def start(self) -> None:
        self.db_writer.start()
        self.network.start()

    def add_network_shutdown_hook(self, hook: Callable[[], Awaitable[None]]) -> None:
        self._network_shutdown_hooks.append(hook)

    async def _shutdown_network_services(self) -> None:
        for hook in self._network_shutdown_hooks:
            try:
                await hook()
            except Exception:
                # Shutdown must continue even if Telegram is already disconnected.
                pass

    def stop(self) -> None:
        if self.network.loop is not None:
            try:
                self.network.submit(self._shutdown_network_services()).result(timeout=8.0)
            except Exception:
                pass
        self.network.stop()
        self.workers.shutdown(wait=True)
        self.db_writer.stop()
