from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from concurrent.futures import Future
import threading
from typing import Any


class NetworkRuntime:
    """Single dedicated asyncio loop for every Telegram client and RPC."""

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.thread_id: int | None = None
        self._ready = threading.Event()

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self._ready.clear()
        self.thread = threading.Thread(
            target=self._run,
            name="TMS-TelegramRuntime",
            daemon=True,
        )
        self.thread.start()
        if not self._ready.wait(5.0):
            raise RuntimeError("Network runtime failed to start")

    def _run(self) -> None:
        self.thread_id = threading.get_ident()
        loop = asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()
            self.loop = None
            self.thread_id = None

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        loop = self.loop
        if loop is None or not loop.is_running():
            raise RuntimeError("Network runtime is not running")
        return asyncio.run_coroutine_threadsafe(coro, loop)

    def assert_network_thread(self) -> None:
        if threading.get_ident() != self.thread_id:
            raise RuntimeError("Telegram operation attempted outside network runtime thread")

    def stop(self) -> None:
        loop = self.loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=8.0)
        self.thread = None
