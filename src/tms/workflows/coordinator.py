from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..core.enums import ActionType, JobState, JobType
from ..core.events import DomainEvent
from ..datasets.models import Dataset
from ..jobs.models import Job
from ..members.filter_spec import FilterSpec
from ..migration.models import MigrationPlanSummary, PrecheckResult


@dataclass(slots=True)
class WorkflowPreview:
    action: ActionType
    job_id: int
    account_id: int
    target_title: str
    target_group_id: int
    coverage: str
    target_count: int
    summary: MigrationPlanSummary


class WorkflowCoordinator:
    """Turn multi-step technical flows into one user-facing operation.

    Resolve/pre-check/plan remain separate backend concepts, but the UI no longer asks
    the user to drive those implementation details manually.
    """

    def __init__(self, context) -> None:
        self.ctx = context

    async def _persist_group(self, group):
        local_id = await asyncio.wrap_future(self.ctx.groups.submit_upsert(group))
        group.local_group_id = local_id
        return group

    async def _ensure_authorized(self, account_id: int) -> None:
        identity = await self.ctx.auth.connect_existing(account_id)
        if identity is None:
            raise RuntimeError(
                "Tài khoản chưa đăng nhập. Vào mục Tài khoản, gửi OTP và đăng nhập trước."
            )

    async def collect_reference(
        self,
        account_id: int,
        reference: str,
        dataset_name: str,
    ) -> tuple[int, int]:
        await self._ensure_authorized(account_id)
        group = await self.ctx.group_service.resolve(account_id, reference)
        group = await self._persist_group(group)
        return await self._collect_group_authorized(account_id, group, dataset_name)

    async def collect_group(
        self,
        account_id: int,
        group,
        dataset_name: str,
    ) -> tuple[int, int]:
        await self._ensure_authorized(account_id)
        return await self._collect_group_authorized(account_id, group, dataset_name)

    async def _collect_group_authorized(
        self,
        account_id: int,
        group,
        dataset_name: str,
    ) -> tuple[int, int]:
        if group.local_group_id is None:
            group = await self._persist_group(group)
        if not group.can_read:
            raise PermissionError("Tài khoản hiện tại không thể đọc thành viên của nhóm này")

        def prepare() -> tuple[int, int]:
            dataset_id = self.ctx.datasets.create(
                Dataset(
                    None,
                    dataset_name.strip() or group.title,
                    "TELEGRAM_GROUP",
                    str(group.telegram_id),
                )
            )
            job_id = self.ctx.jobs.create(
                Job(
                    None,
                    JobType.SCAN,
                    JobState.READY,
                    account_id=account_id,
                    source_dataset_id=dataset_id,
                    target_group_id=group.local_group_id,
                )
            )
            return dataset_id, job_id

        dataset_id, job_id = await asyncio.wrap_future(
            self.ctx.runtime.workers.submit(prepare)
        )
        self.ctx.runtime.events.publish(
            DomainEvent(
                "MemberScanStarted",
                {
                    "job_id": job_id,
                    "dataset_id": dataset_id,
                    "group_title": group.title,
                },
            )
        )
        await self.ctx.scanner.scan(job_id, account_id, group, dataset_id)
        return dataset_id, job_id

    async def _precheck_with_job(
        self,
        account_id: int,
        target,
    ) -> PrecheckResult:
        def create_job() -> int:
            return self.ctx.jobs.create(
                Job(
                    None,
                    JobType.TARGET_SCAN,
                    JobState.RUNNING,
                    account_id=account_id,
                    target_group_id=target.local_group_id,
                )
            )

        job_id = await asyncio.wrap_future(self.ctx.runtime.workers.submit(create_job))
        await asyncio.wrap_future(
            self.ctx.jobs.submit_event(
                job_id,
                "INFO",
                "TARGET_PRECHECK_STARTED",
                f"target={target.telegram_id}",
                critical=True,
            )
        )
        try:
            result = await self.ctx.precheck.run(self.ctx.gateway, account_id, target)
            await asyncio.wrap_future(
                self.ctx.jobs.submit_set_state(
                    job_id,
                    JobState.COMPLETED,
                    checkpoint={
                        "coverage": str(result.coverage),
                        "target_count": len(result.target_ids),
                    },
                )
            )
            await asyncio.wrap_future(
                self.ctx.jobs.submit_event(
                    job_id,
                    "INFO",
                    "TARGET_PRECHECK_COMPLETED",
                    f"coverage={result.coverage} target_count={len(result.target_ids)}",
                    critical=True,
                )
            )
            return result
        except Exception as exc:
            await asyncio.wrap_future(
                self.ctx.jobs.submit_set_state(
                    job_id,
                    JobState.FAILED,
                    checkpoint={"error": str(exc)},
                )
            )
            await asyncio.wrap_future(
                self.ctx.jobs.submit_event(
                    job_id,
                    "ERROR",
                    "TARGET_PRECHECK_FAILED",
                    str(exc),
                    critical=True,
                )
            )
            raise

    async def prepare_action(
        self,
        action: ActionType,
        account_id: int,
        source_dataset_id: int,
        target_reference: str,
        filter_spec: FilterSpec | None = None,
    ) -> WorkflowPreview:
        await self._ensure_authorized(account_id)
        target = await self.ctx.group_service.resolve(account_id, target_reference)
        target = await self._persist_group(target)
        if action == ActionType.INVITE and not target.can_invite:
            raise PermissionError(
                "Tài khoản hiện tại không có quyền thêm thành viên vào nhóm đích"
            )
        if action == ActionType.REMOVE and not target.can_remove:
            raise PermissionError(
                "Tài khoản hiện tại không có quyền xóa thành viên khỏi nhóm này"
            )

        precheck = await self._precheck_with_job(account_id, target)

        def create_plan():
            if action == ActionType.REMOVE:
                return self.ctx.planner.create_remove_plan(
                    account_id,
                    source_dataset_id,
                    target.local_group_id,
                    precheck,
                    filter_spec,
                )
            return self.ctx.planner.create_plan(
                account_id,
                source_dataset_id,
                target.local_group_id,
                precheck,
                filter_spec,
            )

        job_id, summary = await asyncio.wrap_future(
            self.ctx.runtime.workers.submit(create_plan)
        )
        return WorkflowPreview(
            action=action,
            job_id=job_id,
            account_id=account_id,
            target_title=target.title,
            target_group_id=int(target.local_group_id),
            coverage=str(precheck.coverage),
            target_count=len(precheck.target_ids),
            summary=summary,
        )
