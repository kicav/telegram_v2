from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic

from ..core.constants import SCAN_DB_BATCH_SIZE, SCAN_PAGE_LIMIT, SCAN_PAGE_QUEUE_MAX
from ..core.enums import JobState
from ..core.events import DomainEvent
from ..datasets.repository import DatasetRepository
from ..jobs.repository import JobRepository
from ..members.models import Member
from ..members.repository import MemberRepository
from ..runtime.event_bus import EventBus
from ..runtime.resource_governor import ResourceGovernor
from .peer_cache import CachedPeer, PeerCache


@dataclass(slots=True)
class ScanCheckpoint:
    offset: int = 0
    accepted: int = 0
    invalid: int = 0
    cancelled: bool = False


@dataclass(slots=True)
class _PageEnvelope:
    page: list[Member]
    next_offset: int


_SENTINEL = object()


class ParticipantScanner:
    """Bounded producer/consumer member scanner with DBWriter persistence."""

    def __init__(
        self,
        gateway,
        members: MemberRepository,
        datasets: DatasetRepository,
        peers: PeerCache,
        jobs: JobRepository,
        event_bus: EventBus,
        governor: ResourceGovernor,
    ) -> None:
        self.gateway = gateway
        self.members = members
        self.datasets = datasets
        self.peers = peers
        self.jobs = jobs
        self.events = event_bus
        self.governor = governor
        self._cancel_events: dict[int, asyncio.Event] = {}

    async def cancel(self, job_id: int) -> None:
        event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()

    async def scan(
        self,
        job_id: int,
        account_id: int,
        group,
        dataset_id: int,
        checkpoint: ScanCheckpoint | None = None,
    ) -> ScanCheckpoint:
        cp = checkpoint or ScanCheckpoint()
        cancel_event = asyncio.Event()
        self._cancel_events[job_id] = cancel_event
        queue: asyncio.Queue[_PageEnvelope | object] = asyncio.Queue(
            maxsize=SCAN_PAGE_QUEUE_MAX
        )
        seen: set[int] = set()
        started = monotonic()

        await asyncio.wrap_future(
            self.jobs.submit_set_state(
                job_id,
                JobState.RUNNING,
                checkpoint={"offset": cp.offset, "accepted": cp.accepted},
            )
        )
        await asyncio.wrap_future(
            self.jobs.submit_event(
                job_id,
                "INFO",
                "SCAN_STARTED",
                f"offset={cp.offset}",
                critical=True,
            )
        )

        async def producer() -> None:
            offset = cp.offset
            was_cancelled = False
            try:
                async with self.governor.read_slot():
                    async for page in self.gateway.iter_participant_pages(
                        account_id,
                        group,
                        offset,
                        SCAN_PAGE_LIMIT,
                    ):
                        if cancel_event.is_set():
                            break
                        offset += len(page)
                        await queue.put(_PageEnvelope(page=page, next_offset=offset))
            except asyncio.CancelledError:
                was_cancelled = True
                raise
            finally:
                # On normal completion (or producer failure), let the consumer drain the
                # bounded queue. If TaskGroup cancelled us because the consumer failed,
                # never block trying to enqueue a sentinel into an orphaned full queue.
                if not was_cancelled:
                    await queue.put(_SENTINEL)

        async def persist_batch(batch: list[Member], offset: int) -> None:
            if not batch:
                return
            # Account-scoped access hashes are copied into RAM immediately and persisted
            # atomically with member/dataset rows by MemberRepository.
            peers = [
                CachedPeer(
                    account_id=account_id,
                    peer_id=member.telegram_user_id,
                    peer_type="User",
                    access_hash=member.access_hash,
                    username=member.username,
                )
                for member in batch
                if member.telegram_user_id is not None and member.access_hash is not None
            ]
            for peer in peers:
                self.peers.put_memory(peer)
            summary = await asyncio.wrap_future(
                self.members.submit_ingest_batch(
                    dataset_id,
                    batch,
                    source_group_id=group.local_group_id,
                    account_id=account_id,
                    source_label=group.title,
                )
            )
            cp.accepted += summary.accepted
            cp.invalid += summary.invalid
            cp.offset = offset
            await asyncio.wrap_future(
                self.jobs.submit_checkpoint(
                    job_id,
                    {
                        "offset": cp.offset,
                        "accepted": cp.accepted,
                        "invalid": cp.invalid,
                    },
                )
            )
            elapsed = max(0.001, monotonic() - started)
            self.events.publish(
                DomainEvent(
                    "MemberScanProgress",
                    {
                        "job_id": job_id,
                        "offset": cp.offset,
                        "accepted": cp.accepted,
                        "invalid": cp.invalid,
                        "queue_depth": queue.qsize(),
                        "rate_per_sec": round(cp.accepted / elapsed, 2),
                    },
                )
            )

        async def consumer() -> None:
            batch: list[Member] = []
            batch_offset = cp.offset
            while True:
                item = await queue.get()
                if item is _SENTINEL:
                    await persist_batch(batch, batch_offset)
                    return
                envelope = item
                assert isinstance(envelope, _PageEnvelope)
                if cancel_event.is_set():
                    cp.cancelled = True
                for member in envelope.page:
                    uid = member.telegram_user_id
                    if uid is None:
                        batch.append(member)
                        continue
                    if uid in seen:
                        continue
                    seen.add(uid)
                    batch.append(member)
                batch_offset = envelope.next_offset
                if len(batch) >= SCAN_DB_BATCH_SIZE:
                    await persist_batch(batch, batch_offset)
                    batch = []

        try:
            # Structured concurrency guarantees that a failing consumer cancels a blocked
            # producer (and vice versa), preventing bounded-queue shutdown deadlocks.
            async with asyncio.TaskGroup() as task_group:
                task_group.create_task(producer())
                task_group.create_task(consumer())
            cp.cancelled = cp.cancelled or cancel_event.is_set()
            final_state = JobState.CANCELLED if cp.cancelled else JobState.COMPLETED
            await asyncio.wrap_future(
                self.jobs.submit_set_state(
                    job_id,
                    final_state,
                    checkpoint={
                        "offset": cp.offset,
                        "accepted": cp.accepted,
                        "invalid": cp.invalid,
                    },
                )
            )
            await asyncio.wrap_future(
                self.jobs.submit_event(
                    job_id,
                    "INFO",
                    "SCAN_CANCELLED" if cp.cancelled else "SCAN_COMPLETED",
                    f"accepted={cp.accepted} invalid={cp.invalid} offset={cp.offset}",
                    critical=True,
                )
            )
            self.events.publish(
                DomainEvent(
                    "MemberScanCompleted",
                    {
                        "job_id": job_id,
                        "dataset_id": dataset_id,
                        "accepted": cp.accepted,
                        "invalid": cp.invalid,
                        "cancelled": cp.cancelled,
                    },
                )
            )
            return cp
        except Exception as exc:
            await asyncio.wrap_future(
                self.jobs.submit_set_state(
                    job_id,
                    JobState.FAILED,
                    checkpoint={
                        "offset": cp.offset,
                        "accepted": cp.accepted,
                        "invalid": cp.invalid,
                        "error": str(exc),
                    },
                )
            )
            await asyncio.wrap_future(
                self.jobs.submit_event(
                    job_id,
                    "ERROR",
                    "SCAN_FAILED",
                    str(exc),
                    critical=True,
                )
            )
            self.events.publish(
                DomainEvent("JobFailed", {"job_id": job_id, "error": str(exc)})
            )
            raise
        finally:
            self._cancel_events.pop(job_id, None)
