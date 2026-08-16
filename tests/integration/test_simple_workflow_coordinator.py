import asyncio
from types import SimpleNamespace

from tms.accounts.models import Account
from tms.core.enums import ActionType, AccountState, JobType
from tms.datasets.models import Dataset
from tms.groups.service import GroupService
from tms.members.models import Member
from tms.migration.planner import MigrationPlanner
from tms.migration.precheck import TargetPrecheck
from tms.runtime.event_bus import EventBus
from tms.runtime.resource_governor import ResourceGovernor
from tms.runtime.worker_pool import WorkerPool
from tms.telegram.fake_gateway import FakeTelegramGateway
from tms.workflows.coordinator import WorkflowCoordinator


class AuthorizedAuth:
    async def connect_existing(self, account_id):
        return object()


def test_simple_workflow_prepare_hides_resolve_precheck_and_plan(store, tmp_path):
    async def run():
        account_id = store.accounts.create(
            Account(
                None,
                "+84911111111",
                str(tmp_path / "simple.session"),
                status=AccountState.READY,
            )
        )
        dataset_id = store.datasets.create(Dataset(None, "Nguồn test", "TEST"))
        store.members.submit_ingest_batch(
            dataset_id,
            [
                Member(1, "one", access_hash=11),
                Member(2, "two", access_hash=22),
                Member(3, "three", access_hash=33),
            ],
            account_id=account_id,
        ).result(timeout=10)

        gateway = FakeTelegramGateway(pages=[[Member(2, "two")]])
        workers = WorkerPool(1)
        context = SimpleNamespace(
            auth=AuthorizedAuth(),
            group_service=GroupService(gateway),
            groups=store.groups,
            runtime=SimpleNamespace(workers=workers, events=EventBus()),
            datasets=store.datasets,
            jobs=store.jobs,
            scanner=None,
            precheck=TargetPrecheck(ResourceGovernor()),
            gateway=gateway,
            planner=MigrationPlanner(store.db, store.jobs),
        )
        coordinator = WorkflowCoordinator(context)
        try:
            invite = await coordinator.prepare_action(
                ActionType.INVITE, account_id, dataset_id, "target", None
            )
            assert invite.summary.ready == 2
            assert invite.summary.already_target == 1
            assert store.jobs.get(invite.job_id)["job_type"] == str(JobType.MIGRATION)

            # A new fake target pre-check is used for a separate REMOVE preview.
            gateway.pages = [[Member(2, "two"), Member(3, "three")]]
            remove = await coordinator.prepare_action(
                ActionType.REMOVE, account_id, dataset_id, "target", None
            )
            assert remove.summary.ready == 2
            assert remove.summary.not_in_target == 1
            assert store.jobs.get(remove.job_id)["job_type"] == str(JobType.REMOVE)
        finally:
            workers.shutdown()

    asyncio.run(run())
