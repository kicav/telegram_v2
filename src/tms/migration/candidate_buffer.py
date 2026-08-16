from __future__ import annotations

import asyncio
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass

from ..core.constants import CANDIDATE_PREFETCH_MAX, CANDIDATE_PREFETCH_MIN
from ..jobs.repository import JobRepository
from ..members.models import Member
from ..runtime.worker_pool import WorkerPool


@dataclass(slots=True)
class BufferedCandidate:
    ordinal: int
    member: Member
    persisted_attempts: int = 0


class CandidateBuffer:
    """RAM window of migration candidates; database reads happen off the network thread."""

    def __init__(
        self,
        jobs: JobRepository,
        workers: WorkerPool,
        job_id: int,
        account_id: int,
        chunk_size: int = CANDIDATE_PREFETCH_MIN,
    ) -> None:
        self.jobs = jobs
        self.workers = workers
        self.job_id = job_id
        self.account_id = account_id
        self.chunk_size = max(
            CANDIDATE_PREFETCH_MIN,
            min(CANDIDATE_PREFETCH_MAX, chunk_size),
        )
        self.low_watermark = max(50, self.chunk_size // 4)
        self.queue: deque[BufferedCandidate] = deque()
        self.last_loaded = -1
        self._loading: Future | None = None
        self._exhausted = False

    def _submit_fill(self) -> None:
        if self._loading is not None or self._exhausted:
            return
        self._loading = self.workers.submit(
            self.jobs.pending_chunk,
            self.job_id,
            self.account_id,
            self.last_loaded,
            self.chunk_size,
        )

    async def _finish_fill(self) -> None:
        self._submit_fill()
        if self._loading is None:
            return
        rows = await asyncio.wrap_future(self._loading)
        self._loading = None
        if not rows:
            self._exhausted = True
            return
        for row in rows:
            self.queue.append(
                BufferedCandidate(
                    ordinal=int(row["ordinal"]),
                    persisted_attempts=int(row["attempt_count"] or 0),
                    member=Member(
                        telegram_user_id=(
                            int(row["telegram_user_id"])
                            if row["telegram_user_id"] is not None
                            else None
                        ),
                        username=row["username"],
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        phone=row["phone"],
                        bot=bool(row["bot"]),
                        deleted=bool(row["deleted"]),
                        activity_status=row["activity_status"],
                        last_seen=row["last_seen"],
                        access_hash=(
                            int(row["account_access_hash"])
                            if row["account_access_hash"] is not None
                            else None
                        ),
                    ),
                )
            )
        self.last_loaded = int(rows[-1]["ordinal"])

    async def prime(self) -> None:
        if not self.queue and not self._exhausted:
            await self._finish_fill()

    async def pop(self) -> BufferedCandidate | None:
        if not self.queue:
            await self._finish_fill()
        if not self.queue:
            return None
        item = self.queue.popleft()
        if len(self.queue) <= self.low_watermark:
            self._submit_fill()
        return item

    @property
    def depth(self) -> int:
        return len(self.queue)
