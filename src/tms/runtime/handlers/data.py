from __future__ import annotations

import asyncio
from pathlib import Path

from ...core.enums import JobState, JobType
from ...core.events import DomainEvent
from ...telegram.participant_scanner import ScanCheckpoint
from .base import HandlerBase


class DataCommands(HandlerBase):
    def register(self, bus) -> None:
        bus.register("source.joined_groups", self.joined_groups)
        bus.register("source.cancel_scan", self.cancel_scan)
        bus.register("source.resume_scan", self.resume_scan)
        bus.register("dataset.import", self.import_dataset)
        bus.register("dataset.combine", self.combine_dataset)
        bus.register("dataset.select", self.select_dataset)
        bus.register("dataset.export", self.export_dataset)
        # Utility commands are retained as backend capabilities, but are not shown in
        # the simplified V1.1 navigation.
        bus.register("utility.join", self.join_group)
        bus.register("utility.leave", self.leave_group)

    async def _resolve_and_persist(self, account_id: int, reference: str):
        group = await self.ctx.group_service.resolve(account_id, reference)
        local_id = await asyncio.wrap_future(self.ctx.groups.submit_upsert(group))
        group.local_group_id = local_id
        return group

    def joined_groups(self, account_id: int) -> None:
        self._require_enabled_account(account_id)

        async def operation():
            identity = await self.ctx.auth.connect_existing(account_id)
            if identity is None:
                raise RuntimeError("Tài khoản chưa đăng nhập")
            groups = await self.ctx.gateway.get_joined_groups(account_id)
            for group in groups:
                group.local_group_id = await asyncio.wrap_future(
                    self.ctx.groups.submit_upsert(group)
                )
            return groups

        self._submit_network(
            "source.joined_groups",
            operation(),
            lambda groups: self.ctx.runtime.events.publish(
                DomainEvent("JoinedGroupsLoaded", {"account_id": account_id, "groups": groups})
            ),
        )

    def cancel_scan(self, job_id: int) -> None:
        self._submit_network("source.cancel_scan", self.ctx.scanner.cancel(job_id))

    def resume_scan(self, job_id: int) -> None:
        row = self.ctx.jobs.get(job_id)
        if row is None or str(row["job_type"]) != str(JobType.SCAN):
            raise ValueError("Không tìm thấy công việc lấy thành viên")
        if str(row["state"]) not in {str(JobState.READY), str(JobState.PAUSED)}:
            raise ValueError("Chỉ scan đã chuẩn bị/tạm dừng mới có thể tiếp tục")
        if (
            row["account_id"] is None
            or row["source_dataset_id"] is None
            or row["target_group_id"] is None
        ):
            raise ValueError("Scan thiếu thông tin tài khoản/dataset/group")
        account_id = int(row["account_id"])
        self._require_enabled_account(account_id)
        dataset_id = int(row["source_dataset_id"])
        group = self.ctx.groups.get(int(row["target_group_id"]), account_id)
        if group is None:
            raise ValueError("Không tìm thấy thông tin nhóm nguồn")
        checkpoint_data = self.ctx.jobs.get_checkpoint(job_id)
        checkpoint = ScanCheckpoint(
            offset=int(checkpoint_data.get("offset", 0) or 0),
            accepted=int(checkpoint_data.get("accepted", 0) or 0),
            invalid=int(checkpoint_data.get("invalid", 0) or 0),
        )
        self._submit_network(
            "source.resume_scan",
            self.ctx.scanner.scan(job_id, account_id, group, dataset_id, checkpoint),
        )

    def stop_scan(self, job_id: int) -> None:
        row = self.ctx.jobs.get(job_id)
        if row is None or str(row["job_type"]) != str(JobType.SCAN):
            raise ValueError("Không tìm thấy công việc lấy thành viên")
        state = str(row["state"])
        if state == str(JobState.RUNNING):
            self.cancel_scan(job_id)
            return
        if state in {str(JobState.PAUSED), str(JobState.READY)}:
            def cancel_persisted() -> None:
                self.ctx.jobs.submit_set_state(
                    job_id, JobState.CANCELLED, clear_waiting=True
                ).result(timeout=10.0)
                self.ctx.jobs.submit_event(
                    job_id, "INFO", "SCAN_CANCELLED", critical=True
                ).result(timeout=10.0)

            self._submit_worker(
                "source.stop_scan",
                cancel_persisted,
                lambda _x: self.ctx.runtime.events.publish(
                    DomainEvent(
                        "JobStateChanged",
                        {"job_id": job_id, "state": str(JobState.CANCELLED), "waiting_until": None},
                    )
                ),
            )
            return
        raise ValueError("Công việc này không thể dừng")

    def import_dataset(
        self,
        path: str,
        name: str,
        account_id: int | None = None,
    ) -> None:
        self._submit_worker(
            "dataset.import",
            lambda: self.ctx.import_export.import_dataset(
                Path(path), name, account_id=account_id
            ),
        )

    def combine_dataset(self, name: str, a_id: int, b_id: int, operation: str) -> None:
        def done(dataset_id: int) -> None:
            self.ctx.state.update(source_dataset_id=dataset_id)
            self.ctx.runtime.events.publish(
                DomainEvent("DatasetCreated", {"dataset_id": dataset_id})
            )

        self._submit_worker(
            "dataset.combine",
            lambda: self.ctx.dataset_service.combine(name, a_id, b_id, operation),
            done,
        )

    def select_dataset(self, dataset_id: int) -> None:
        self.ctx.state.update(source_dataset_id=dataset_id)
        self.ctx.runtime.events.publish(
            DomainEvent("ActiveDatasetChanged", {"dataset_id": dataset_id})
        )

    def export_dataset(
        self,
        dataset_id: int,
        path: str,
        account_id: int | None = None,
    ) -> None:
        if self.ctx.runtime.governor.performance_mode:
            self.ctx.runtime.events.publish(
                DomainEvent(
                    "BackgroundTaskDeferred",
                    {"task": "export", "reason": "Đang ưu tiên xử lý thành viên"},
                )
            )
            return
        self._submit_worker(
            "dataset.export",
            lambda: self.ctx.import_export.export_dataset(
                dataset_id, Path(path), account_id=account_id
            ),
        )

    def join_group(self, account_id: int, reference: str) -> None:
        self._require_enabled_account(account_id)
        self._submit_network(
            "utility.join",
            self.ctx.membership.join(account_id, reference),
            lambda group: self.ctx.runtime.events.publish(
                DomainEvent("UtilityCompleted", {"action": "join", "group": group})
            ),
        )

    def leave_group(self, account_id: int, reference: str) -> None:
        self._require_enabled_account(account_id)

        async def operation():
            group = await self._resolve_and_persist(account_id, reference)
            await self.ctx.membership.leave(account_id, group)
            return group

        self._submit_network(
            "utility.leave",
            operation(),
            lambda group: self.ctx.runtime.events.publish(
                DomainEvent("UtilityCompleted", {"action": "leave", "group": group})
            ),
        )
