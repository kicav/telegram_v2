from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from ...core.enums import ActionType, JobState, JobType
from ...core.events import DomainEvent
from ...members.filter_spec import FilterSpec
from ...migration.executor import MemberActionExecutor
from ...migration.scheduler import InviteScheduler
from .base import HandlerBase


class WorkflowCommands(HandlerBase):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._executors: dict[int, MemberActionExecutor] = {}

    def register(self, bus) -> None:
        bus.register("workflow.collect", self.workflow_collect)
        bus.register("workflow.collect_group", self.workflow_collect_group)
        bus.register("workflow.invite.prepare", self.workflow_prepare_invite)
        bus.register("workflow.remove.prepare", self.workflow_prepare_remove)
        bus.register("action.start", self.start_action)
        bus.register("action.pause", self.pause_action)
        bus.register("action.stop", self.stop_action)
        bus.register("action.resume", self.resume_action)
        bus.register("action.cancel_prepared", self.cancel_prepared_action)

    def is_action_active(self, job_id: int) -> bool:
        return job_id in self._executors

    async def prepare_shutdown(self, timeout: float = 3.0) -> None:
        executors = list(self._executors.values())
        for executor in executors:
            await executor.request_pause()
        if not executors:
            return
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.0, timeout)
        while loop.time() < deadline:
            if all(executor._running_job_id is None for executor in executors):
                return
            await asyncio.sleep(0.05)

    @staticmethod
    def _remaining_wait(waiting_until: str | None) -> float:
        if not waiting_until:
            return 0.0
        try:
            wait_dt = datetime.fromisoformat(str(waiting_until))
        except ValueError:
            return 0.0
        if wait_dt.tzinfo is None:
            wait_dt = wait_dt.replace(tzinfo=timezone.utc)
        return max(0.0, (wait_dt - datetime.now(timezone.utc)).total_seconds())

    def _apply_account_server_wait(
        self, executor: MemberActionExecutor, account_id: int
    ) -> None:
        remaining = self._remaining_wait(self.ctx.jobs.account_waiting_until(account_id))
        if remaining > 0:
            executor.scheduler.apply_server_wait(remaining)

    def _new_executor(
        self,
        job_id: int,
        interval: float,
        action: ActionType,
    ) -> MemberActionExecutor:
        executor = MemberActionExecutor(
            self.ctx.gateway,
            self.ctx.jobs,
            self.ctx.accounts,
            self.ctx.runtime.governor,
            self.ctx.runtime.events,
            InviteScheduler(interval),
            self.ctx.runtime.workers,
            self.ctx.metrics,
            action_type=action,
        )
        self._executors[job_id] = executor
        return executor

    def _ensure_account_free(self, account_id: int) -> None:
        active = self.ctx.jobs.active_job_for_account(account_id)
        if active:
            raise RuntimeError(
                "Tài khoản đang có công việc chưa hoàn tất. Hãy hoàn thành hoặc dừng công việc đó trước."
            )

    def workflow_collect(
        self,
        account_id: int,
        reference: str,
        dataset_name: str = "",
    ) -> None:
        self._require_enabled_account(account_id)
        self._ensure_account_free(account_id)
        if not reference.strip():
            raise ValueError("Hãy nhập link hoặc @username của nhóm nguồn")
        self._submit_network(
            "workflow.collect",
            self.ctx.workflows.collect_reference(
                account_id, reference.strip(), dataset_name.strip()
            ),
        )

    def workflow_collect_group(
        self,
        account_id: int,
        group,
        dataset_name: str = "",
    ) -> None:
        self._require_enabled_account(account_id)
        self._ensure_account_free(account_id)
        self._submit_network(
            "workflow.collect_group",
            self.ctx.workflows.collect_group(account_id, group, dataset_name.strip()),
        )

    def _prepare_action(
        self,
        action: ActionType,
        account_id: int,
        source_dataset_id: int,
        target_reference: str,
        filter_spec: FilterSpec | None,
    ) -> None:
        self._require_enabled_account(account_id)
        self._ensure_account_free(account_id)
        if not target_reference.strip():
            raise ValueError("Hãy nhập link hoặc @username của nhóm đích")

        def done(preview) -> None:
            self.ctx.state.update(
                source_dataset_id=source_dataset_id,
                migration_job_id=preview.job_id,
                plan_summary=preview.summary,
            )
            self.ctx.runtime.events.publish(
                DomainEvent("WorkflowActionPrepared", {"preview": preview})
            )

        self._submit_network(
            f"workflow.{str(action).lower()}.prepare",
            self.ctx.workflows.prepare_action(
                action,
                account_id,
                source_dataset_id,
                target_reference.strip(),
                filter_spec,
            ),
            done,
        )

    def workflow_prepare_invite(
        self,
        account_id: int,
        source_dataset_id: int,
        target_reference: str,
        filter_spec: FilterSpec | None = None,
    ) -> None:
        self._prepare_action(
            ActionType.INVITE,
            account_id,
            source_dataset_id,
            target_reference,
            filter_spec,
        )

    def workflow_prepare_remove(
        self,
        account_id: int,
        source_dataset_id: int,
        target_reference: str,
        filter_spec: FilterSpec | None = None,
    ) -> None:
        self._prepare_action(
            ActionType.REMOVE,
            account_id,
            source_dataset_id,
            target_reference,
            filter_spec,
        )

    def _action_from_job(self, row) -> ActionType:
        return (
            ActionType.REMOVE
            if str(row["job_type"]) == str(JobType.REMOVE)
            else ActionType.INVITE
        )

    def start_action(
        self,
        job_id: int,
        account_id: int,
        interval_seconds: float,
    ) -> None:
        if job_id in self._executors:
            raise RuntimeError("Công việc này đang chạy")
        self._require_enabled_account(account_id)
        active = self.ctx.jobs.active_job_for_account(account_id)
        if active and int(active["id"]) != job_id:
            raise RuntimeError("Tài khoản đang có một công việc khác chưa hoàn tất")
        row = self.ctx.jobs.get(job_id)
        if row is None or str(row["job_type"]) not in {
            str(JobType.MIGRATION),
            str(JobType.REMOVE),
        }:
            raise ValueError("Không tìm thấy công việc thêm/xóa thành viên")
        if str(row["state"]) != str(JobState.READY):
            raise ValueError("Chỉ công việc đã chuẩn bị mới có thể bắt đầu")
        if row["account_id"] is None or int(row["account_id"]) != account_id:
            raise ValueError("Tài khoản không khớp với công việc")
        self._run_persisted_action(row, interval_seconds, "action.start")

    def _run_persisted_action(self, row, interval_seconds: float, command: str) -> None:
        job_id = int(row["id"])
        account_id = int(row["account_id"])
        if row["target_group_id"] is None:
            raise ValueError("Công việc thiếu thông tin nhóm đích")
        target = self.ctx.groups.get(int(row["target_group_id"]), account_id)
        if target is None:
            raise ValueError("Không tìm thấy thông tin nhóm đích")
        action = self._action_from_job(row)
        target.can_invite = action == ActionType.INVITE
        target.can_remove = action == ActionType.REMOVE
        executor = self._new_executor(job_id, interval_seconds, action)
        self._apply_account_server_wait(executor, account_id)
        self._submit_network(
            command,
            executor.run(job_id, account_id, target),
            on_finished=lambda: self._executors.pop(job_id, None),
        )

    def cancel_prepared_action(self, job_id: int) -> None:
        row = self.ctx.jobs.get(job_id)
        if row is None or str(row["state"]) != str(JobState.READY):
            return

        def cancel() -> None:
            self.ctx.jobs.submit_set_state(
                job_id, JobState.CANCELLED, clear_waiting=True
            ).result(timeout=10.0)
            self.ctx.jobs.submit_event(
                job_id,
                "INFO",
                "ACTION_PREVIEW_CANCELLED",
                "Prepared action was not confirmed by the user",
                critical=True,
            ).result(timeout=10.0)

        self._submit_worker(
            "action.cancel_prepared",
            cancel,
            lambda _x: self.ctx.runtime.events.publish(
                DomainEvent(
                    "JobStateChanged",
                    {
                        "job_id": job_id,
                        "state": str(JobState.CANCELLED),
                        "waiting_until": None,
                    },
                )
            ),
        )

    def pause_action(self, job_id: int) -> None:
        executor = self._executors.get(job_id)
        if executor is None:
            raise ValueError("Công việc hiện không chạy")
        self._submit_network("action.pause", executor.request_pause())

    def stop_action(self, job_id: int) -> None:
        executor = self._executors.get(job_id)
        if executor is not None:
            self._submit_network("action.stop", executor.request_stop())
            return
        row = self.ctx.jobs.get(job_id)
        if row is None:
            raise ValueError("Không tìm thấy công việc")
        if str(row["state"]) not in {
            str(JobState.READY),
            str(JobState.PAUSED),
            str(JobState.WAITING_SERVER),
        }:
            raise ValueError("Công việc hiện không thể dừng")

        def cancel_persisted() -> None:
            self.ctx.jobs.submit_set_state(
                job_id, JobState.CANCELLED, clear_waiting=True
            ).result(timeout=10.0)
            self.ctx.jobs.submit_event(
                job_id, "INFO", "ACTION_CANCELLED", critical=True
            ).result(timeout=10.0)

        self._submit_worker(
            "action.stop",
            cancel_persisted,
            lambda _x: self.ctx.runtime.events.publish(
                DomainEvent(
                    "JobStateChanged",
                    {
                        "job_id": job_id,
                        "state": str(JobState.CANCELLED),
                        "waiting_until": None,
                    },
                )
            ),
        )

    def resume_action(self, job_id: int, interval_seconds: float) -> None:
        if job_id in self._executors:
            raise RuntimeError("Công việc này đang chạy")
        row = self.ctx.jobs.get(job_id)
        if row is None or str(row["job_type"]) not in {
            str(JobType.MIGRATION),
            str(JobType.REMOVE),
        }:
            raise ValueError("Không tìm thấy công việc thêm/xóa thành viên")
        if str(row["state"]) not in {
            str(JobState.READY),
            str(JobState.PAUSED),
            str(JobState.WAITING_SERVER),
        }:
            raise ValueError("Chỉ công việc đã chuẩn bị/tạm dừng/đang chờ mới có thể tiếp tục")
        if row["account_id"] is None:
            raise ValueError("Công việc thiếu thông tin tài khoản")
        account_id = int(row["account_id"])
        self._require_enabled_account(account_id)
        active = self.ctx.jobs.active_job_for_account(account_id)
        if active and int(active["id"]) != job_id:
            raise RuntimeError("Tài khoản đang có một công việc khác chưa hoàn tất")
        self._run_persisted_action(row, interval_seconds, "action.resume")
