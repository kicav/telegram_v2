import asyncio

from tms.accounts.models import Account
from tms.core.clock import FakeClock
from tms.core.enums import JobState, JobType, TargetCoverage
from tms.datasets.models import Dataset
from tms.groups.models import GroupContext
from tms.jobs.models import Job
from tms.members.models import Member
from tms.migration.executor import MigrationExecutor
from tms.migration.planner import MigrationPlanner
from tms.migration.precheck import TargetPrecheck
from tms.migration.scheduler import InviteScheduler
from tms.runtime.event_bus import EventBus
from tms.runtime.resource_governor import ResourceGovernor
from tms.runtime.worker_pool import WorkerPool
from tms.telegram.fake_gateway import FakeTelegramGateway
from tms.telegram.participant_scanner import ParticipantScanner


class UserPrivacyRestrictedError(Exception):
    pass


def test_scan_precheck_plan_and_migrate_core_workflow(store, tmp_path):
    async def run():
        account_id = store.accounts.create(
            Account(None, "+84666666", str(tmp_path / "e2e.session"))
        )
        source_group = GroupContext(
            1000, 10000, "Source", "source", "Channel", True, True, True, True
        )
        source_group.local_group_id = store.groups.upsert(source_group)
        dataset_id = store.datasets.create(Dataset(None, "source", "TELEGRAM_GROUP"))
        scan_job = store.jobs.create(
            Job(
                None,
                JobType.SCAN,
                JobState.READY,
                account_id=account_id,
                source_dataset_id=dataset_id,
                target_group_id=source_group.local_group_id,
            )
        )
        source_gateway = FakeTelegramGateway(
            pages=[
                [
                    Member(1, "one", access_hash=11),
                    Member(2, "two", access_hash=22),
                    Member(3, "three", access_hash=33),
                ]
            ]
        )
        governor = ResourceGovernor()
        await ParticipantScanner(
            source_gateway,
            store.members,
            store.datasets,
            store.peers,
            store.jobs,
            EventBus(),
            governor,
        ).scan(scan_job, account_id, source_group, dataset_id)

        target = GroupContext(
            2000, 20000, "Target", "target", "Channel", True, True, True, True
        )
        target.local_group_id = store.groups.upsert(target)
        precheck = await TargetPrecheck(governor).run(
            FakeTelegramGateway(pages=[[Member(2, "two")]]), account_id, target
        )
        assert precheck.coverage == TargetCoverage.COMPLETE
        assert precheck.target_ids == {2}

        migration_job, summary = MigrationPlanner(store.db, store.jobs).create_plan(
            account_id,
            dataset_id,
            target.local_group_id,
            precheck,
        )
        assert summary.ready == 2
        assert summary.already_target == 1

        migration_gateway = FakeTelegramGateway(
            invite_effects=[UserPrivacyRestrictedError("privacy"), None]
        )
        workers = WorkerPool(1)
        try:
            await MigrationExecutor(
                migration_gateway,
                store.jobs,
                store.accounts,
                governor,
                EventBus(),
                InviteScheduler(5, FakeClock()),
                workers,
            ).run(migration_job, account_id, target)
        finally:
            workers.shutdown()

        result = store.jobs.summary(migration_job)
        assert migration_gateway.invites == [1, 3]
        assert result == {
            "total": 2,
            "processed": 2,
            "success": 1,
            "skipped": 1,
            "failed": 0,
        }
        assert store.jobs.get(migration_job)["state"] == JobState.COMPLETED

    asyncio.run(run())
