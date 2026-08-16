import asyncio

from tms.accounts.models import Account
from tms.core.enums import JobState, JobType
from tms.datasets.models import Dataset
from tms.groups.models import GroupContext
from tms.jobs.models import Job
from tms.members.models import Member
from tms.runtime.event_bus import EventBus
from tms.runtime.resource_governor import ResourceGovernor
from tms.telegram.fake_gateway import FakeTelegramGateway
from tms.telegram.participant_scanner import ParticipantScanner


def test_scanner_bounded_pipeline_deduplicates_and_persists_access_hashes(store, tmp_path):
    async def run():
        account_id = store.accounts.create(
            Account(None, "+84444444", str(tmp_path / "scan.session"))
        )
        group = GroupContext(
            777, 888, "source", "source", "Channel", True, True, True, True
        )
        group.local_group_id = store.groups.upsert(group)
        dataset_id = store.datasets.create(Dataset(None, "scan", "TELEGRAM_GROUP"))
        job_id = store.jobs.create(
            Job(
                None,
                JobType.SCAN,
                JobState.READY,
                account_id=account_id,
                source_dataset_id=dataset_id,
                target_group_id=group.local_group_id,
            )
        )
        pages = [
            [Member(1, "one", access_hash=101), Member(2, "two", access_hash=102)],
            [Member(2, "two2", access_hash=102), Member(3, "three", access_hash=103)],
        ]
        scanner = ParticipantScanner(
            FakeTelegramGateway(pages=pages),
            store.members,
            store.datasets,
            store.peers,
            store.jobs,
            EventBus(),
            ResourceGovernor(),
        )
        checkpoint = await scanner.scan(job_id, account_id, group, dataset_id)
        assert checkpoint.accepted == 3
        assert checkpoint.invalid == 0
        assert store.datasets.get(dataset_id).member_count == 3
        assert store.jobs.get(job_id)["state"] == JobState.COMPLETED
        assert store.peers.get(account_id, 1).access_hash == 101
        assert store.peers.get(account_id, 3).access_hash == 103

    asyncio.run(run())
