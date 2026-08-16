import asyncio

from tms.accounts.models import Account
from tms.core.clock import FakeClock
from tms.core.enums import JobState, TargetCoverage
from tms.core.events import DomainEvent
from tms.datasets.models import Dataset
from tms.groups.models import GroupContext
from tms.members.models import Member
from tms.migration.executor import MigrationExecutor
from tms.migration.models import PrecheckResult
from tms.migration.planner import MigrationPlanner
from tms.migration.scheduler import InviteScheduler
from tms.runtime.event_bus import EventBus
from tms.runtime.resource_governor import ResourceGovernor
from tms.runtime.worker_pool import WorkerPool
from tms.telegram.fake_gateway import FakeTelegramGateway


class FloodWaitError(Exception):
    def __init__(self, seconds: int):
        super().__init__(f"FLOOD_WAIT_{seconds}")
        self.seconds = seconds


class UserPrivacyRestrictedError(Exception):
    pass


class ChatAdminRequiredError(Exception):
    pass


async def _build_job(store, tmp_path, members):
    account_id = store.accounts.create(
        Account(None, "+84333333", str(tmp_path / "m.session"))
    )
    source_id = store.datasets.create(Dataset(None, "source", "FILE"))
    store.members.submit_ingest_batch(
        source_id, members, account_id=account_id
    ).result(timeout=10)
    target = GroupContext(
        99,
        999,
        "target",
        "target",
        "Channel",
        True,
        True,
        True,
        True,
        True,
    )
    group_id = store.groups.upsert(target)
    target.local_group_id = group_id
    job_id, _summary = MigrationPlanner(store.db, store.jobs).create_plan(
        account_id,
        source_id,
        group_id,
        PrecheckResult(set(), TargetCoverage.COMPLETE),
    )
    return account_id, job_id, target


def test_executor_one_candidate_per_invite_and_no_target_reresolve(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store,
            tmp_path,
            [Member(1, "a", access_hash=11), Member(2, "b", access_hash=22)],
        )
        fake = FakeTelegramGateway()
        clock = FakeClock()
        workers = WorkerPool(1)
        try:
            executor = MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, clock),
                workers,
            )
            await executor.run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.invites == [1, 2]
        assert fake.resolve_calls == 0
        assert clock.now == 5
        assert store.jobs.get(job_id)["state"] == JobState.COMPLETED

    asyncio.run(run())


def test_floodwait_resumes_same_candidate_without_account_rotation(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(10, "a", access_hash=110)]
        )
        fake = FakeTelegramGateway(invite_effects=[FloodWaitError(120), None])
        clock = FakeClock()
        workers = WorkerPool(1)
        try:
            executor = MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, clock),
                workers,
            )
            await executor.run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.invites == [10, 10]
        assert clock.now >= 120
        assert store.jobs.get(job_id)["success"] == 1

    asyncio.run(run())


def test_privacy_is_terminal_skip(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(20, "a", access_hash=220)]
        )
        fake = FakeTelegramGateway(invite_effects=[UserPrivacyRestrictedError("privacy")])
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        summary = store.jobs.summary(job_id)
        assert summary["skipped"] == 1
        assert summary["failed"] == 0

    asyncio.run(run())


def test_permission_pauses_and_candidate_remains_retryable(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(30, "a", access_hash=330)]
        )
        fake = FakeTelegramGateway(invite_effects=[ChatAdminRequiredError("denied")])
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert store.jobs.get(job_id)["state"] == JobState.PAUSED
        with store.db.reader() as conn:
            state = conn.execute(
                "SELECT state FROM migration_items WHERE job_id=?", (job_id,)
            ).fetchone()[0]
        assert state == "RETRY"

    asyncio.run(run())


def test_transient_errors_retry_three_attempts_with_1_2_4_policy(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(40, "a", access_hash=440)]
        )
        fake = FakeTelegramGateway(
            invite_effects=[
                ConnectionError("net-1"),
                ConnectionError("net-2"),
                ConnectionError("net-3"),
            ]
        )
        clock = FakeClock()
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, clock),
                workers,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.invites == [40, 40, 40]
        assert clock.now == 14
        row = store.jobs.get(job_id)
        assert row["state"] == JobState.COMPLETED_WITH_ERRORS
        assert row["failed"] == 1
        with store.db.reader() as conn:
            attempts = conn.execute(
                "SELECT attempt_count FROM migration_items WHERE job_id=?", (job_id,)
            ).fetchone()[0]
        assert attempts == 3

    asyncio.run(run())


class PeerFloodError(Exception):
    pass


def test_indefinite_rate_limit_pauses_without_automatic_retry(store, tmp_path):
    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(50, "a", access_hash=550)]
        )
        fake = FakeTelegramGateway(invite_effects=[PeerFloodError("restricted")])
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.invites == [50]
        assert store.jobs.get(job_id)["state"] == JobState.PAUSED
        event = store.jobs.last_event(job_id)
        assert event is not None
        assert event["event_code"] == "RATE_LIMIT_PAUSED"

    asyncio.run(run())


def test_remove_action_reuses_bounded_candidate_pipeline(store, tmp_path):
    from tms.core.enums import ActionType, JobType
    from tms.jobs.models import Job
    from tms.migration.executor import MemberActionExecutor

    async def run():
        account_id = store.accounts.create(
            Account(None, "+84444444", str(tmp_path / "r.session"))
        )
        source_id = store.datasets.create(Dataset(None, "source-remove", "FILE"))
        store.members.submit_ingest_batch(
            source_id,
            [Member(60, "remove-me", access_hash=660)],
            account_id=account_id,
        ).result(timeout=10)
        target = GroupContext(
            199,
            1999,
            "target-remove",
            "target-remove",
            "Channel",
            True,
            True,
            True,
            True,
            True,
            can_remove=True,
        )
        group_id = store.groups.upsert(target)
        target.local_group_id = group_id
        job_id = store.jobs.create(
            Job(
                None,
                JobType.REMOVE,
                JobState.READY,
                account_id=account_id,
                source_dataset_id=source_id,
                target_group_id=group_id,
                total=1,
            )
        )
        with store.db.reader() as conn:
            member_id = int(
                conn.execute(
                    "SELECT member_id FROM dataset_members WHERE dataset_id=?",
                    (source_id,),
                ).fetchone()[0]
            )
        store.jobs.submit_add_items(job_id, [(member_id, "KNOWN_PRESENT")]).result(timeout=10)
        fake = FakeTelegramGateway()
        workers = WorkerPool(1)
        try:
            await MemberActionExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
                action_type=ActionType.REMOVE,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.removes == [60]
        assert store.jobs.get(job_id)["state"] == JobState.COMPLETED
        assert store.jobs.get(job_id)["success"] == 1

    asyncio.run(run())


def test_rpc_watchdog_prevents_permanent_busy_hang(store, tmp_path):
    class SlowGateway(FakeTelegramGateway):
        async def invite_user(self, account_id, target, member):
            self.invites.append(member.telegram_user_id)
            await asyncio.sleep(0.1)

    async def run():
        account_id, job_id, target = await _build_job(
            store, tmp_path, [Member(70, "slow", access_hash=770)]
        )
        fake = SlowGateway()
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                fake,
                store.jobs,
                store.accounts,
                ResourceGovernor(),
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
                rpc_timeout_seconds=0.01,
            ).run(job_id, account_id, target)
        finally:
            workers.shutdown()
        assert fake.invites == [70, 70, 70]
        row = store.jobs.get(job_id)
        assert row["state"] == JobState.COMPLETED_WITH_ERRORS
        assert row["failed"] == 1

    asyncio.run(run())
