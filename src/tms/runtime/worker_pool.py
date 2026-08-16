from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


class WorkerPool:
    """Bounded workers for file I/O and large local transformations."""

    def __init__(self, workers: int = 2) -> None:
        self.executor = ThreadPoolExecutor(
            max_workers=max(1, workers),
            thread_name_prefix="TMS-FileWorker",
        )

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[Any]:
        return self.executor.submit(fn, *args, **kwargs)

    def shutdown(self, *, wait: bool = True) -> None:
        # Running imports/exports can still have DBWriter work in flight. Waiting here
        # lets those tasks finish before the single SQLite writer is stopped.
        self.executor.shutdown(wait=wait, cancel_futures=True)
