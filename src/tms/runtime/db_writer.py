from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from queue import Empty, Queue
import sqlite3
import threading
from typing import Any, Generic, TypeVar, cast

from ..storage.database import Database

T = TypeVar("T")


@dataclass(slots=True)
class _WriteTask(Generic[T]):
    operation: Callable[[sqlite3.Connection], T]
    future: Future[T]
    critical: bool = False


_STOP = object()


class DBWriter:
    """Single SQLite writer pipeline.

    Routine operations are coalesced into one transaction. Critical state transitions
    flush immediately. Callers receive a ``Future`` so the network loop can await a write
    with ``asyncio.wrap_future`` instead of blocking the Telegram thread.
    """

    def __init__(
        self,
        database: Database,
        batch_limit: int = 250,
        flush_interval: float = 0.25,
        queue_limit: int = 5000,
    ) -> None:
        self.database = database
        self.batch_limit = max(1, batch_limit)
        self.flush_interval = max(0.01, flush_interval)
        self._queue: Queue[_WriteTask[Any] | object] = Queue(maxsize=queue_limit)
        self._thread: threading.Thread | None = None
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._thread_id: int | None = None

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    @property
    def thread_id(self) -> int | None:
        return self._thread_id

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopped.clear()
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="TMS-DBWriter",
            daemon=True,
        )
        self._thread.start()
        if not self._started.wait(timeout=5.0):
            raise RuntimeError("DBWriter failed to start")

    def submit(
        self,
        operation: Callable[[sqlite3.Connection], T],
        *,
        critical: bool = False,
    ) -> Future[T]:
        if self._stopped.is_set():
            future: Future[T] = Future()
            future.set_exception(RuntimeError("DBWriter has been stopped"))
            return future
        if not self._thread or not self._thread.is_alive():
            self.start()
        future = Future[T]()
        self._queue.put(_WriteTask(operation=operation, future=future, critical=critical))
        return future

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        *,
        critical: bool = False,
    ) -> Future[int]:
        def operation(conn: sqlite3.Connection) -> int:
            cursor = conn.execute(sql, params)
            return int(cursor.rowcount)

        return self.submit(operation, critical=critical)

    def flush(self, timeout: float = 10.0) -> None:
        self.submit(lambda _conn: None, critical=True).result(timeout=timeout)

    def stop(self, timeout: float = 10.0) -> None:
        if not self._thread:
            self._stopped.set()
            return
        try:
            self.flush(timeout=timeout)
        except Exception:
            # Shutdown still proceeds; pending futures receive any DB exception in _run.
            pass
        self._queue.put(_STOP)
        self._thread.join(timeout=timeout)
        self._stopped.set()

    @staticmethod
    def _fail_tasks(tasks: list[_WriteTask[Any]], exc: BaseException) -> None:
        for task in tasks:
            if not task.future.done():
                task.future.set_exception(exc)

    def _commit_batch(
        self,
        conn: sqlite3.Connection,
        tasks: list[_WriteTask[Any]],
    ) -> None:
        if not tasks:
            return
        results: list[Any] = []
        try:
            conn.execute("BEGIN IMMEDIATE")
            for task in tasks:
                results.append(task.operation(conn))
            conn.commit()
        except BaseException as exc:
            conn.rollback()
            self._fail_tasks(tasks, exc)
            return
        for task, result in zip(tasks, results, strict=True):
            if not task.future.done():
                cast(Future[Any], task.future).set_result(result)

    def _run(self) -> None:
        self._thread_id = threading.get_ident()
        conn = self.database.connect()
        self._started.set()
        pending: list[_WriteTask[Any]] = []
        try:
            while True:
                try:
                    item = self._queue.get(timeout=self.flush_interval)
                except Empty:
                    self._commit_batch(conn, pending)
                    pending.clear()
                    continue

                if item is _STOP:
                    self._commit_batch(conn, pending)
                    pending.clear()
                    break

                task = cast(_WriteTask[Any], item)
                if task.critical:
                    self._commit_batch(conn, pending)
                    pending.clear()
                    self._commit_batch(conn, [task])
                    continue

                pending.append(task)
                if len(pending) >= self.batch_limit:
                    self._commit_batch(conn, pending)
                    pending.clear()
        finally:
            if pending:
                self._commit_batch(conn, pending)
            conn.close()
