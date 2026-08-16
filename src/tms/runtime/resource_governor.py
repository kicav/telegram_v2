from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from threading import RLock


class ResourceGovernor:
    """Coordinates Telegram mutation/read capacity and migration Performance Mode."""

    def __init__(self, max_reads: int = 3) -> None:
        self._mutation_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._read_semaphore = asyncio.Semaphore(max(1, max_reads))
        self._performance_users = 0
        self._lock = RLock()

    def mutation_lock(self, account_id: int) -> asyncio.Lock:
        return self._mutation_locks[account_id]

    @asynccontextmanager
    async def read_slot(self):
        await self._read_semaphore.acquire()
        try:
            yield
        finally:
            self._read_semaphore.release()

    @property
    def performance_mode(self) -> bool:
        with self._lock:
            return self._performance_users > 0

    def enable_performance_mode(self) -> None:
        with self._lock:
            self._performance_users += 1

    def disable_performance_mode(self) -> None:
        with self._lock:
            self._performance_users = max(0, self._performance_users - 1)
